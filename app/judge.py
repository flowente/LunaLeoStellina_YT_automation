"""Giudice visivo (controllo tecnico + artistico) con un modello OpenAI con la vista.
Riceve: character sheet ufficiali, griglia di 32 fotogrammi con il tempo, sceneggiatura (FRAMING/ACTION/RULES),
misure automatiche (qc.py) e le tolleranze decise da Simone. Restituisce un verdetto JSON con i rifacimenti."""
import base64, json, io
from pathlib import Path
import cv2, numpy as np, requests
from . import config, episodes

SHEETS = ["characters/luna_sheet_CANON.png", "characters/leo_sheet_CANON.png", "characters/stella_sheet_CANON.png"]

RULES = """Sei il CONTROLLORE ARTISTICO e TECNICO del canale di short 3D per bambini 1-4 anni "Luna, Leo e Stellina".
Regole del canale:
1. Identità come gli sheet: Luna = tuta intera, chignon con elastici corallo, NIENTE gonnellino/tutù; Leo = ciuffo che esce dal casco, accenti verde menta; Stellina = stella gialla con faccina, SENZA braccia né gambe, UNA sola.
2. Azione shot per shot come da sceneggiatura (chi fa cosa, colori e oggetti giusti, conteggi giusti, gesti richiesti: un abbraccio non deve diventare un bacio; nessun conteggio con un numero sbagliato di dita).
3. FRAMING rispettato (dimensioni, lato sinistra/destra, camera ferma se richiesta, niente partenza larga con zoom).
4. Nessuna deformazione, duplicazione, oggetto che cambia colore, testo generato, saluto alla camera (salvo che la sceneggiatura lo preveda).
5. LOOP: l'ultimo fotogramma deve essere quasi uguale al primo (posizioni, pose, espressioni).
6. Ambientazione: sempre Marte all'esterno.
TOLLERANZE (decise dal proprietario): sono TRASCURABILI e NON richiedono rifacimento i difetti lievi < 1 s che non toccano identità né azione
(luci/scintille che velano o tingono per un attimo i personaggi, un oggetto che passa brevemente davanti a Stellina, piccole trasparenze durante uno scoppio,
piccole differenze di dimensione). Da correggere SEMPRE: loop, identità diversa dagli sheet, azione sbagliata, duplicazioni, deformazioni evidenti, testo generato.
Non inventare: se non sei sicuro scrivi "sospetto"."""

SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["verdetto", "shots", "loop", "trascurabili", "rifacimento"],
          "properties": {
              "verdetto": {"type": "string", "enum": ["APPROVATO", "APPROVATO CON RISERVA", "DA RIFARE"]},
              "shots": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                        "required": ["id", "ok", "problemi"],
                        "properties": {"id": {"type": "string"}, "ok": {"type": "boolean"},
                                       "problemi": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                    "required": ["secondo", "descrizione", "gravita"],
                                                    "properties": {"secondo": {"type": "number"}, "descrizione": {"type": "string"},
                                                                   "gravita": {"type": "string", "enum": ["alta", "media", "bassa"]}}}}}}},
              "loop": {"type": "string"},
              "trascurabili": {"type": "array", "items": {"type": "string"}},
              "rifacimento": {"type": ["object", "null"], "additionalProperties": False,
                              "required": ["da_secondo", "istruzioni_prompt"],
                              "properties": {"da_secondo": {"type": "number"}, "istruzioni_prompt": {"type": "string"}}}}}


def _b64(img_bgr, q=85):
    ok, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, q])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def grid(video: Path, n=32, cols=8):
    cap = cv2.VideoCapture(str(video)); fps = cap.get(cv2.CAP_PROP_FPS) or 24
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); dur = total / fps; tiles = []
    for k in range(n):
        t = k * dur / n; cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps)); ok, f = cap.read()
        if not ok: f = np.zeros((284, 160, 3), np.uint8)
        f = cv2.resize(f, (200, 356)); cv2.putText(f, f"{t:.1f}s", (5, 18), 0, 0.55, (255, 255, 255), 2)
        tiles.append(f)
    last = cap.set(cv2.CAP_PROP_POS_FRAMES, total - 1); ok, lf = cap.read()
    if ok:
        lf = cv2.resize(lf, (200, 356)); cv2.putText(lf, f"FINE {dur:.1f}s", (5, 18), 0, 0.55, (0, 255, 255), 2); tiles[-1] = lf
    rows = [np.hstack(tiles[r * cols:(r + 1) * cols]) for r in range(n // cols)]
    return np.vstack(rows)


def judge(video: Path, ep_id: str, qc_report: dict):
    if not config.OPENAI_API_KEY: raise RuntimeError("OPENAI_API_KEY non impostata")
    E, req = episodes.request_for(ep_id)
    p = req["input"]["prompt"]
    script = p[p.find("FRAMING"):p.find("STYLE")] + "\n" + p[p.find("ACTION"):p.find("AUDIO")]
    shots = [f"{s['id']} = {s['t0']:g}-{s['t1']:g}s" for s in episodes.shots(E)]
    misure = {k: qc_report.get(k) for k in ("loop", "camera", "global_issues")}
    misure["shots"] = [{"id": s["id"], "problemi": s["problemi"], "personaggi": s["personaggi_chiave"]} for s in qc_report.get("shots", [])]
    content = [{"type": "input_text", "text": RULES + "\n\nSHOT: " + ", ".join(shots) + "\n\nSCENEGGIATURA:\n" + script +
                "\n\nMISURE AUTOMATICHE (indicative, il riconoscimento dei personaggi può sbagliare):\n" + json.dumps(misure, ensure_ascii=False) +
                "\n\nNell'ordine: i 3 character sheet (Luna, Leo, Stellina), poi la griglia di 32 fotogrammi in ordine (tempo in alto a sinistra; l'ultima casella è l'ULTIMO fotogramma). Rispondi in italiano."}]
    for s in SHEETS:
        content.append({"type": "input_image", "image_url": episodes.SUPA_REFS + s})
    content.append({"type": "input_image", "image_url": _b64(grid(video))})
    body = {"model": config.OPENAI_MODEL, "input": [{"role": "user", "content": content}],
            "text": {"format": {"type": "json_schema", "name": "verdetto_video", "schema": SCHEMA, "strict": True}}}
    r = requests.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                      json=body, timeout=300)
    r.raise_for_status(); j = r.json()
    text = j.get("output_text") or "".join(c.get("text", "") for o in j.get("output", []) for c in o.get("content", []) if c.get("type") == "output_text")
    usage = j.get("usage", {})
    cost = (usage.get("input_tokens", 0) * config.OPENAI_PRICE_IN + usage.get("output_tokens", 0) * config.OPENAI_PRICE_OUT) / 1e6
    return json.loads(text), usage, round(cost, 4)
