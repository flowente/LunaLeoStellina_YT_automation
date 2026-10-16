"""Storyboard in bianco e nero (matita) di un episodio: un pannello per ogni shot del prompt.

Flusso (Telegram):
  /storyboard EP032          -> disegna i pannelli (Nano Banana Pro su Kie) e manda la tavola con le info da approvare
  /storyboard EP032 3 nota   -> rifà solo il pannello 3 con la correzione
  Approva                    -> da qui in poi /bozza passa a Seedance anche lo storyboard (striscia pulita, senza scritte)

Stile: l'immagine di Simone su Supabase (STYLE_REF) dà tratto e disegno di Luna, Leo e Stellina; i character sheet
canonici, il set e le tavole prop danno i dettagli. Le scritte della tavola (tempi, camera, azione, colori) le aggiunge
il codice, mai il modello: sono sempre esatte e nei disegni non c'è testo che Seedance possa copiare.
"""
import json, re, textwrap, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont
from . import config, episodes, kie, costs, storage

STYLE_REF = config.env("STORYBOARD_STYLE_REF", "storyboard/stile_storyboard.png")   # nel bucket delle tavole
MODEL = config.env("STORYBOARD_MODEL", "nano-banana-pro")
RESOLUTION = config.env("STORYBOARD_RESOLUTION", "1K")
MAX_REFS = 8                                                                      # limite di Nano Banana Pro

COLORS = {"RED": ("rosso", (226, 54, 54)), "BLUE": ("blu", (40, 110, 230)), "YELLOW": ("giallo", (250, 205, 30)),
          "GREEN": ("verde", (40, 175, 80)), "PURPLE": ("viola", (140, 70, 200)), "ORANGE": ("arancione", (245, 135, 30)),
          "PINK": ("rosa", (240, 120, 180))}

PENCIL = ("Draw ONE single storyboard panel as a BLACK AND WHITE PENCIL SKETCH on white paper, exactly in the drawing style of Image 1: "
          "soft graphite lines, light hatching for shading, clean children's-book storyboard look, NO color at all, a thin dark frame "
          "border around the panel. Absolutely NO text, NO numbers, NO letters, NO captions, NO speech bubbles inside the drawing. "
          "Only small motion lines or a curved arrow when something moves.")


def _ref_url(path):
    return episodes.SUPA_REFS + path


def _ok(url):
    try: return requests.head(url, timeout=20).status_code == 200
    except Exception: return False


def plan(ep):
    """Episodio -> shot, riferimenti e informazioni per la tavola."""
    m, eps = episodes.all_episodes()
    if ep not in eps: raise KeyError(f"Episodio {ep} non definito")
    E = eps[ep]; wide = E.get("aspect") == "16:9"
    shots = episodes.shots(E)
    if not shots: raise RuntimeError(f"{ep}: nessuno shot con tempi (0-1s: ...) nelle azioni")
    world = E["world"] + ("_16x9" if wide else "")
    refs = [("style", STYLE_REF)] + [(c, m.REFS[c]) for c in E["cast"]] + [(p, m.REFS[p]) for p in E.get("props", [])] + [(world, m.REFS[world])]
    refs = refs[:MAX_REFS - 1]                      # un posto resta al pannello 1 (continuità)
    missing = [p for k, p in refs if not _ok(_ref_url(p))]
    return dict(E=E, m=m, wide=wide, shots=shots, refs=refs, missing=missing, aspect=E.get("aspect", "9:16"))


def _cast_text(P):
    m, E = P["m"], P["E"]; names = {"luna": m.LUNA, "leo": m.LEO, "stellina": m.STELLINA}
    lines = []
    for i, (k, _) in enumerate(P["refs"], 1):
        if k == "style": lines.append(f"Image {i} = THE STYLE REFERENCE: a pencil storyboard of Luna, Leo and Stellina. Draw the characters EXACTLY as they are drawn there (same pencil design, proportions, faces, helmets).")
        elif k in names: lines.append(f"Image {i} = color character sheet, use it only to check design details (do NOT copy its colors or 3D look): " + names[k].format(img=f"Image {i}").lstrip("- "))
        elif k.startswith("mars_"): lines.append(f"Image {i} = the set: redraw this exact Mars place as a light pencil sketch (same dunes, crater, rocks, rocket or rover, sky).")
        else: lines.append(f"Image {i} = prop sheet: draw these objects with the same shape and size, in pencil.")
    if E.get("props_text"):
        t = E["props_text"]
        for i, (k, _) in enumerate(P["refs"], 1): t = t.replace("{" + k + "}", f"Image {i}")
        lines.append("PROPS: " + t.replace("{leo_img}", "the Leo sheet"))
    return "\n".join(lines)


def panel_prompt(P, shot, note="", continuity=False):
    E = P["E"]; n = len(P["refs"]) + 1
    who = ", ".join(c.capitalize() for c in E["cast"])
    txt = [PENCIL,
           f"Format: {'horizontal 16:9' if P['wide'] else 'vertical 9:16'} panel, camera at the children's eye level. "
           + ("All characters and the action stay inside the CENTRAL THIRD of the panel width. " if P["wide"] else ""),
           _cast_text(P),
           (f"Image {n} = panel 1 of this same storyboard: keep the SAME drawing style, framing, set and character sizes." if continuity else ""),
           "FRAMING (same in every panel unless the action says otherwise): " + re.sub(r"^FRAMING:\s*", "", E.get("framing", "")),
           f"THIS PANEL shows the key moment of {shot['t0']:g}-{shot['t1']:g}s: {shot['text']}",
           f"Characters in the scene: {who}. Only ONE Stellina, she has NO arms and NO legs. Helmets always on.",
           f"EXTRA NOTE FROM THE DIRECTOR: {note}" if note else ""]
    return "\n\n".join(t for t in txt if t)


def _kie_image(prompt, urls, aspect, log):
    req = {"model": MODEL, "input": {"prompt": prompt[:9500], "image_input": urls, "aspect_ratio": aspect,
                                     "resolution": RESOLUTION, "output_format": "png"}}
    task = kie.create(req); log(f"storyboard task {task}")
    url, d = kie.wait(task, timeout_s=10 * 60, log=log)
    return url, task, d


def captions(P):
    """Didascalie in italiano (OpenAI, modello economico). Se manca la chiave restano in inglese."""
    shots = P["shots"]
    base = [dict(id=s["id"], titolo="", azione=s["text"], camera="fissa", inquadratura="") for s in shots]
    if not config.OPENAI_API_KEY: return base, 0
    schema = {"type": "object", "additionalProperties": False, "required": ["shots"], "properties": {"shots": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["id", "titolo", "azione", "camera", "inquadratura"],
        "properties": {"id": {"type": "string"}, "titolo": {"type": "string"}, "azione": {"type": "string"},
                       "camera": {"type": "string"}, "inquadratura": {"type": "string"}}}}}}
    E = P["E"]
    prompt = ("Sei l'aiuto regista di un cartone per bambini. Per ogni shot scrivi in ITALIANO: titolo (2-4 parole), azione (una frase "
              "breve e concreta: chi fa cosa, dove), camera (es. 'fissa', 'segue Leo lenta'), inquadratura (es. 'campo medio, bambini 40%'). "
              "Non inventare nulla che non ci sia.\n\nCAMERA: " + (E.get("camera") or "static, no movement") +
              "\nFRAMING: " + E.get("framing", "") + "\nSHOT:\n" + "\n".join(f"{s['id']} {s['t0']:g}-{s['t1']:g}s: {s['text']}" for s in shots))
    body = {"model": config.OPENAI_IDEAS_MODEL, "input": [{"role": "user", "content": prompt}],
            "text": {"format": {"type": "json_schema", "name": "didascalie", "schema": schema, "strict": True}}}
    try:
        r = requests.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                          json=body, timeout=120)
        r.raise_for_status(); j = r.json()
        text = j.get("output_text") or "".join(c.get("text", "") for o in j.get("output", []) for c in o.get("content", []) if c.get("type") == "output_text")
        out = {x["id"]: x for x in json.loads(text)["shots"]}
        return [out.get(b["id"], b) for b in base], config.openai_cost(j.get("usage", {}), config.OPENAI_IDEAS_MODEL)
    except Exception as e:
        print("didascalie storyboard:", e); return base, 0


# ------------------------------------------------------------------ tavola
def _font(size, bold=False):
    f = config.FONTS / ("Inter-SemiBold.otf" if bold else "Inter-Regular.otf")
    return ImageFont.truetype(str(f), size)


def _colors_in(text):
    return [COLORS[c] for c in COLORS if re.search(rf"\b{c}\b", text.upper())]


def compose(P, panels, caps, out_sheet: Path, out_strip: Path, ep):
    """Tavola per Simone (con tutte le informazioni) + striscia pulita per Seedance (solo disegni numerati)."""
    E = P["E"]; wide = P["wide"]
    pw, ph = (560, 315) if wide else (330, 587)
    per_row = 3 if wide else 5
    gap, cap_h, head_h, pad = 24, 270, 150, 36
    rows = (len(panels) + per_row - 1) // per_row
    W = pad * 2 + per_row * pw + (per_row - 1) * gap
    H = head_h + rows * (ph + cap_h + gap) + pad
    sheet = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(sheet)
    props = E.get("props", [])
    d.text((pad, 28), f"{ep} · {E['title']}", font=_font(38, True), fill="black")
    d.text((pad, 80), f"Durata {E['duration']} s · {P['aspect']} · set {E['world']} · cast: {', '.join(E['cast'])}"
           + (f" · prop: {', '.join(props)}" if props else "") + (" · azione nel terzo centrale" if wide else ""),
           font=_font(22), fill=(60, 60, 60))
    d.text((pad, 112), "Camera: " + ("fissa (nessun movimento)" if not E.get("camera") else E["camera"][:120]),
           font=_font(20), fill=(90, 90, 90))
    d.line((pad, head_h - 12, W - pad, head_h - 12), fill=(30, 30, 30), width=2)
    for i, (img, sh, cp) in enumerate(zip(panels, P["shots"], caps)):
        r, c = divmod(i, per_row)
        x = pad + c * (pw + gap); y = head_h + r * (ph + cap_h + gap)
        im = Image.open(img).convert("RGB"); im = im.resize((pw, ph))
        sheet.paste(im, (x, y)); d.rectangle((x, y, x + pw - 1, y + ph - 1), outline="black", width=2)
        if wide:                                                     # guide del terzo centrale (solo sulla tavola)
            for gx in (x + pw // 3, x + 2 * pw // 3):
                for gy in range(y, y + ph, 14): d.line((gx, gy, gx, gy + 6), fill=(150, 150, 150), width=1)
        d.rectangle((x, y, x + 64, y + 40), fill="black"); d.text((x + 10, y + 7), str(i + 1), font=_font(24, True), fill="white")
        ty = y + ph + 10
        d.text((x, ty), f"{sh['id']} · {sh['t0']:g}–{sh['t1']:g} s" + (f" · {cp['titolo']}" if cp.get("titolo") else ""),
               font=_font(21, True), fill="black")
        cx = x
        for name, rgb in _colors_in(sh["text"]):
            d.ellipse((cx, ty + 36, cx + 22, ty + 58), fill=rgb, outline="black")
            d.text((cx + 28, ty + 36), name, font=_font(17), fill="black"); cx += 40 + int(d.textlength(name, font=_font(17)))
        yy = ty + (66 if cx > x else 36)
        d.text((x, yy), f"Camera: {cp.get('camera') or 'fissa'}", font=_font(17), fill=(70, 70, 70)); yy += 24
        chars = max(20, int(pw / 9.2))
        for line in textwrap.wrap(cp.get("azione") or sh["text"], chars)[:7]:
            d.text((x, yy), line, font=_font(17), fill="black"); yy += 22
        if i == len(panels) - 1 and not E.get("no_loop"):
            d.text((x, yy + 4), "↺ loop: finisce come il pannello 1", font=_font(17, True), fill=(40, 110, 230))
    sheet.save(out_sheet, optimize=True)
    # striscia pulita per Seedance: solo pannelli in ordine, con il numero nell'angolo (nessuna didascalia)
    sw = pw * len(panels) + 12 * (len(panels) - 1)
    strip = Image.new("RGB", (sw, ph), "white"); ds = ImageDraw.Draw(strip)
    for i, img in enumerate(panels):
        x = i * (pw + 12); strip.paste(Image.open(img).convert("RGB").resize((pw, ph)), (x, 0))
        ds.rectangle((x, 0, x + 34, 30), fill="black"); ds.text((x + 9, 2), str(i + 1), font=_font(20, True), fill="white")
    strip.save(out_strip, optimize=True)
    return out_sheet, out_strip


# ------------------------------------------------------------------ generazione
def generate(ep, ep_dir: Path, st: dict, log, only=None, note=""):
    """Disegna (o ridisegna il pannello `only`) e compone la tavola. Restituisce il dizionario da salvare nello stato."""
    P = plan(ep)
    if P["missing"]:
        raise RuntimeError("Mancano su Supabase: " + ", ".join(P["missing"]) +
                           (f"  (carica il tuo storyboard di stile come {STYLE_REF})" if STYLE_REF in P["missing"] else ""))
    sb = dict(st.get("storyboard") or {})
    prev = {p["id"]: p for p in sb.get("panels", [])} if only else {}
    ver = int(sb.get("version", 0)) + 1
    d = ep_dir / "storyboard"; d.mkdir(parents=True, exist_ok=True)
    urls = [_ref_url(p) for _, p in P["refs"]]
    before = kie.credit(); tasks = []

    def draw(i, cont_url=None):
        sh = P["shots"][i]
        pr = panel_prompt(P, sh, note if (only is None or only == i + 1) else "", continuity=bool(cont_url))
        url, task, info = _kie_image(pr, urls + ([cont_url] if cont_url else []), P["aspect"], log)
        f = d / f"{ep}_sb_v{ver:02d}_{sh['id']}.png"; kie.download(url, f)
        tasks.append((task, info.get("creditsConsumed")))
        return {"id": sh["id"], "t0": sh["t0"], "t1": sh["t1"], "file": f.name, "kie_url": url, "note": note if only == i + 1 else ""}

    n = len(P["shots"])
    if only:
        if not 1 <= only <= n: raise RuntimeError(f"{ep} ha {n} pannelli: scegli tra 1 e {n}")
        if not prev: raise RuntimeError(f"{ep}: nessuno storyboard da correggere, lancia prima /storyboard {ep}")
        first = prev.get(P["shots"][0]["id"], {}).get("kie_url")
        new = draw(only - 1, first if only > 1 else None)
        panels = [new if s["id"] == new["id"] else prev[s["id"]] for s in P["shots"]]
    else:
        p1 = draw(0)
        with ThreadPoolExecutor(4) as ex:
            rest = list(ex.map(lambda i: draw(i, p1["kie_url"]), range(1, n)))
        panels = [p1] + rest
    after = kie.credit()
    used = sum(float(c) for _, c in tasks if c not in (None, "")) or ((before - after) if before and after else "")
    costs.record(episodio=ep, take="", tipo=f"storyboard v{ver} ({len(tasks)} pannelli)", servizio="kie", modello=MODEL,
                 risoluzione=RESOLUTION, crediti=used, esito="ok", task_id=",".join(t for t, _ in tasks), credito_residuo=after)
    caps, cap_cost = (sb.get("captions"), 0) if only and sb.get("captions") else captions(P)
    if cap_cost: costs.record(episodio=ep, tipo="didascalie storyboard", servizio="openai", modello=config.OPENAI_IDEAS_MODEL, costo_usd=cap_cost, esito="ok")
    sheet, strip = compose(P, [d / p["file"] for p in panels], caps,
                           d / f"{ep}_storyboard_v{ver:02d}.png", d / f"{ep}_storyboard_v{ver:02d}_seedance.png", ep)
    pre = f"{config.SUPABASE_VIDEO_PREFIX}/{config.CHANNEL}/{ep}/storyboard"
    sheet_url = storage.upload(sheet, f"{pre}/{sheet.name}"); strip_url = storage.upload(strip, f"{pre}/{strip.name}")
    usd = round(float(used) * config.KIE_CREDIT_USD, 2) if used not in ("", None) else None
    return {"version": ver, "approved": False, "sheet": sheet.name, "sheet_url": sheet_url, "strip": strip.name, "strip_url": strip_url,
            "panels": panels, "captions": caps, "cost_usd": usd, "created": time.strftime("%Y-%m-%dT%H:%M:%S")}


# ------------------------------------------------------------------ uso nella bozza
def seedance_block(tag, n_panels, shots):
    times = ", ".join(f"panel {i} = {s['t0']:g}-{s['t1']:g}s" for i, s in enumerate(shots, 1))
    return ("STORYBOARD: " + tag + f" is the approved black-and-white pencil storyboard of THIS video: {n_panels} numbered panels "
            f"from left to right, one per time block ({times}). Follow it for composition, character positions, poses, sizes in the "
            "frame and the order of the actions. IGNORE its drawing style: it is only a pencil sketch with no colors. Rendering, colors, "
            "character design and set come ONLY from the other reference images, as described above. The video never shows pencil "
            "lines, paper texture, panel borders, numbers or text.")
