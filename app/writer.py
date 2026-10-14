"""Scrittore di episodi per il comando Telegram /nuovo: da un'idea breve a un episodio completo nel formato di eps.py.
Usa OpenAI con le regole del canale e due episodi riusciti come esempio."""
import json, re
import requests
from . import config, episodes

RULES = """Scrivi un episodio per il canale YouTube Shorts "Luna, Leo e Stellina" (bambini 1-4 anni, cartoni 3D).
Personaggi: Luna (bambina astronauta, chignon con elastici corallo, tuta intera, mai gonnellino), Leo (fratellino, ciuffo che esce dal casco, accenti menta),
Stellina (stella gialla luminosa con faccina, SENZA braccia né gambe, si muove solo fluttuando, girando, brillando; ce n'è UNA sola).
Regole OBBLIGATORIE:
- Sempre su Marte, all'esterno. world = mars_A (razzo bianco a sinistra), mars_B (dune, cratere a destra, Terra nel cielo) o mars_C (rover a sinistra, pianeta con anelli).
- Durata 12 secondi (15 solo se ci sono tre ripetizioni che lo richiedono). Azioni in inglese, a blocchi di tempo "0-1s: ...", "1-4s: ...", fino alla durata esatta.
- Struttura: aggancio immediato (personaggi già in scena e in movimento al primo fotogramma), ripetizioni "una alla volta", finale che torna ESATTAMENTE alla posa e posizione iniziali (loop perfetto), niente saluto alla camera.
- Format interattivi: colori, contare, imitazione. Oggetti grandi vicino ai bambini; niente oggetti piccoli in cielo, niente conteggi con le dita, niente giravolte complicate.
- COLORI: oggetti, vernici, pozzanghere e schizzi sempre a campiture PIENE, opache, sature e ben definite (come i sassi e i cestini di EP006); trasparenti solo bolle o luci.
- Nessuna scritta nel video. Nessun prop complesso che richieda una tavola di riferimento (niente animali, veicoli nuovi, strumenti, cibo con forme precise): solo luci, bolle, pozzanghere, nuvolette, scintille, gocce di colore, sassi.
- Regole esplicite per evitare scambi: chi tocca cosa, quanti oggetti, i colori non cambiano da soli.
- Se la tuta si sporca o cambia colore per la storia, nel finale torna pulita (per il loop) e va scritto chiaramente.
- Audio in inglese: musica originale strumentale, effetti, risatine; nessun titolo di canzone, nessuna parola. La musica chiude sulla stessa nota con cui inizia.
- title_it e title_en con emoji pertinenti; per la stella usa SOLO ⭐; termina con " | ... per bambini #shorts" (IT) e " | ... for Toddlers #shorts" (EN). In inglese Stellina si chiama "Stella".
- desc_it / desc_en: 1-2 frasi che raccontano il video, con ⭐; MAI la frequenza di pubblicazione, MAI inviti a iscriversi.
- framing: frase inglese "FRAMING: medium shot, the SAME framing from the very first frame to the last (no zoom, no push-in). ..." con posizioni (Luna a sinistra, Leo a destra), bambini circa 40% dell'altezza, piedi circa 18% dal basso.
- rules: inizia con "RULES: " in inglese.
- cover_s: secondo con l'azione più bella per la copertina."""

SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["title", "slug", "duration", "cast", "world", "goal", "framing", "action", "rules", "audio",
                       "title_it", "title_en", "desc_it", "desc_en", "cover_s", "riassunto_it"],
          "properties": {
              "title": {"type": "string"}, "slug": {"type": "string"},
              "duration": {"type": "integer", "enum": [12, 15]},
              "cast": {"type": "array", "items": {"type": "string", "enum": ["luna", "leo", "stellina"]}},
              "world": {"type": "string", "enum": ["mars_A", "mars_B", "mars_C"]},
              "goal": {"type": "string"}, "framing": {"type": "string"},
              "action": {"type": "array", "items": {"type": "string"}},
              "rules": {"type": "string"}, "audio": {"type": "string"},
              "title_it": {"type": "string"}, "title_en": {"type": "string"},
              "desc_it": {"type": "string"}, "desc_en": {"type": "string"},
              "cover_s": {"type": "number"},
              "riassunto_it": {"type": "string", "description": "3-5 righe in italiano per Simone: cosa succede shot per shot"}}}


def next_id():
    _, eps = episodes.all_episodes()
    n = max(int(k[2:]) for k in eps if re.fullmatch(r"EP\d+", k)) + 1
    return f"EP{n:03d}"


def write(idea: str, feedback: str = ""):
    if not config.OPENAI_API_KEY: raise RuntimeError("OPENAI_API_KEY non impostata")
    _, eps = episodes.all_episodes()
    examples = {k: {f: eps[k][f] for f in SCHEMA["properties"] if f in eps[k]} for k in ("EP026", "EP010") if k in eps}
    prompt = (RULES + "\n\nESEMPI di episodi riusciti (stesso formato):\n" + json.dumps(examples, ensure_ascii=False) +
              f"\n\nIDEA DI SIMONE: {idea}" + (f"\nCORREZIONI RICHIESTE: {feedback}" if feedback else ""))
    body = {"model": config.OPENAI_MODEL, "input": [{"role": "user", "content": prompt}],
            "text": {"format": {"type": "json_schema", "name": "episodio", "schema": SCHEMA, "strict": True}}}
    r = requests.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                      json=body, timeout=180)
    r.raise_for_status(); j = r.json()
    text = j.get("output_text") or "".join(c.get("text", "") for o in j.get("output", []) for c in o.get("content", []) if c.get("type") == "output_text")
    spec = json.loads(text)
    usage = j.get("usage", {})
    cost = (usage.get("input_tokens", 0) * config.OPENAI_PRICE_IN + usage.get("output_tokens", 0) * config.OPENAI_PRICE_OUT) / 1e6
    return spec, usage, round(cost, 4)


def revise(spec: dict, change: str):
    """Applica una correzione di Simone a un episodio esistente, lasciando invariato tutto il resto."""
    if not config.OPENAI_API_KEY: raise RuntimeError("OPENAI_API_KEY non impostata")
    base = {f: spec[f] for f in SCHEMA["properties"] if f in spec}
    base.setdefault("riassunto_it", "")
    prompt = (RULES + "\n\nEPISODIO ATTUALE (JSON):\n" + json.dumps(base, ensure_ascii=False) +
              f"\n\nCORREZIONE DI SIMONE: {change}\n\nRiscrivi l'episodio applicando SOLO questa correzione: modifica le azioni, le regole e "
              "i testi coinvolti in modo preciso ed esplicito per Seedance; lascia identico tutto il resto (durata, mondo, inquadratura, titoli se non toccati). "
              "In riassunto_it scrivi in 2-3 righe cosa hai cambiato.")
    body = {"model": config.OPENAI_MODEL, "input": [{"role": "user", "content": prompt}],
            "text": {"format": {"type": "json_schema", "name": "episodio", "schema": SCHEMA, "strict": True}}}
    r = requests.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                      json=body, timeout=180)
    r.raise_for_status(); j = r.json()
    text = j.get("output_text") or "".join(c.get("text", "") for o in j.get("output", []) for c in o.get("content", []) if c.get("type") == "output_text")
    usage = j.get("usage", {})
    cost = (usage.get("input_tokens", 0) * config.OPENAI_PRICE_IN + usage.get("output_tokens", 0) * config.OPENAI_PRICE_OUT) / 1e6
    return json.loads(text), usage, round(cost, 4)


# ------------------------------------------------------------------ brainstorming (/idee e /brainstorming)
CONCEPTS = {"type": "object", "additionalProperties": False, "required": ["idee"],
            "properties": {"idee": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["titolo", "descrizione"],
                "properties": {"titolo": {"type": "string"}, "descrizione": {"type": "string"}}}}}}

BRAIN = {"type": "object", "additionalProperties": False, "required": ["risposta", "titolo", "descrizione"],
         "properties": {"risposta": {"type": "string", "description": "2-5 righe in italiano: cosa hai capito, cosa proponi, al massimo 1-2 domande"},
                        "titolo": {"type": "string"}, "descrizione": {"type": "string"}}}

IDEA_RULES = """Lavori come autore del canale. Le idee devono essere realizzabili con le REGOLE del canale (sotto) e in 12 secondi.
Ogni idea: titolo italiano breve (con al massimo un'emoji, per la stella solo ⭐) e una descrizione di 2-3 righe in italiano
che dica cosa fanno Luna, Leo e Stellina, quale gioco o concetto imparano (colori, contare, imitazione...) e come il finale torna all'inizio (loop).
Prendi spunto dai format degli episodi esistenti (elenco sotto) ma non ripeterli: varia oggetto, gioco o concetto."""


def _catalog():
    _, eps = episodes.all_episodes()
    return "\n".join(f"- {k}: {v.get('title', '')}: {str(v.get('goal', ''))[:140]}" for k, v in sorted(eps.items()))


def _call(prompt, schema, name):
    if not config.OPENAI_API_KEY: raise RuntimeError("OPENAI_API_KEY non impostata")
    body = {"model": config.OPENAI_MODEL, "input": [{"role": "user", "content": prompt}],
            "text": {"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}}}
    r = requests.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                      json=body, timeout=180)
    r.raise_for_status(); j = r.json()
    text = j.get("output_text") or "".join(c.get("text", "") for o in j.get("output", []) for c in o.get("content", []) if c.get("type") == "output_text")
    usage = j.get("usage", {})
    cost = (usage.get("input_tokens", 0) * config.OPENAI_PRICE_IN + usage.get("output_tokens", 0) * config.OPENAI_PRICE_OUT) / 1e6
    return json.loads(text), usage, round(cost, 4)


def concepts(tema: str = "", n: int = 5):
    """/idee: n idee già pronte (titolo + descrizione) ispirate agli episodi esistenti."""
    prompt = (IDEA_RULES + f"\n\nREGOLE DEL CANALE:\n{RULES}\n\nEPISODI ESISTENTI:\n{_catalog()}\n\n"
              f"Proponi {n} idee nuove" + (f" sul tema: {tema}" if tema else " varie (colori, contare, imitazione, buone maniere)") + ".")
    out, usage, cost = _call(prompt, CONCEPTS, "idee")
    return out["idee"][:n], usage, cost


def brainstorm(history: list):
    """/brainstorming: conversazione. history = [{"chi": "simone"|"autore", "testo": ...}]. Restituisce risposta + pacchetto aggiornato."""
    talk = "\n".join(f"{'SIMONE' if h['chi'] == 'simone' else 'TU'}: {h['testo']}" for h in history)
    prompt = (IDEA_RULES + f"\n\nREGOLE DEL CANALE:\n{RULES}\n\nEPISODI ESISTENTI:\n{_catalog()}\n\n"
              "Stai facendo brainstorming con Simone su UN episodio. Parti dalla sua idea abbozzata e definiscila: rendila realizzabile, "
              "chiara e adatta a bambini di 1-4 anni. Se un suo desiderio viola le regole (es. animali, interni, scritte), dillo e proponi "
              "l'alternativa più vicina. Rispondi breve. Ogni volta restituisci anche il 'pacchetto' aggiornato: titolo e descrizione, "
              f"sempre completi.\n\nCONVERSAZIONE:\n{talk}")
    return _call(prompt, BRAIN, "brainstorming")
