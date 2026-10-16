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
# Chi disegna: "openai" (default, tavola intera in una sola immagine, come in ChatGPT) oppure "kie" (un pannello alla volta)
PROVIDER = (config.env("STORYBOARD_PROVIDER", "openai") or "openai").lower()
OPENAI_IMAGE_MODEL = config.env("STORYBOARD_OPENAI_MODEL", "gpt-image-2")
OPENAI_IMAGE_QUALITY = config.env("STORYBOARD_OPENAI_QUALITY", "high")
OPENAI_IMAGE_COST = float(config.env("STORYBOARD_OPENAI_COST_USD", "0.25"))     # stima per tavola, finché non c'è il listino nel codice

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
def generate_kie(ep, ep_dir: Path, st: dict, log, only=None, note=""):
    """Kie: un'immagine per pannello, poi la tavola composta dal codice."""
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
            f"read in order 1, 2, 3... (each panel has its number in the top-left corner), one per time block ({times}). Follow it for composition, character positions, poses, sizes in the "
            "frame and the order of the actions. IGNORE its drawing style: it is only a pencil sketch with no colors. Rendering, colors, "
            "character design and set come ONLY from the other reference images, as described above. The video never shows pencil "
            "lines, paper texture, panel borders, numbers or text.")


# ------------------------------------------------------------------ OpenAI: tavola intera in una sola immagine
LAYOUT_HINT = {1: "one panel", 2: "two panels side by side", 3: "three panels side by side", 4: "two rows of two panels",
               5: "top row: panels 1, 2, 3; bottom row: panels 4, 5 (centered)", 6: "top row: panels 1, 2, 3; bottom row: panels 4, 5, 6"}


def sheet_prompt(P, note="", redo_panel=None):
    E = P["E"]; n = len(P["shots"]); wide = P["wide"]
    names = {k: i for i, (k, _) in enumerate(P["refs"], 1)}
    det = ", ".join(f"{k.replace('_', ' ')} (image {i})" for k, i in names.items() if k != "style")
    lay = LAYOUT_HINT.get(n, f"{n} panels in rows of 3, in reading order")
    if wide: lay = {4: "two rows of two panels", 6: "three rows of two panels"}.get(n, f"{n} panels in rows of 2, in reading order")
    lines = [
        f"Create a storyboard sheet for a {E['duration']}-second {'horizontal 16:9' if wide else 'vertical 9:16'} toddler cartoon "
        + ("clip (part of a longer video)." if wide else "short."),
        "STYLE: exactly the drawing style of the FIRST attached image: black and white pencil sketch on white paper, soft graphite lines, "
        "light hatching, clean children's-book storyboard look. NO color anywhere. Draw Luna, Leo and Stellina exactly as they are drawn "
        f"in the first image (same pencil design, faces, helmets, proportions). The other images are only for checking details: {det}. "
        "Redraw everything in pencil; never copy their colors or 3D look.",
        f"LAYOUT: one sheet with {n} panels: {lay}. EVERY PANEL IS A "
        + ("HORIZONTAL 16:9 FRAME (wider than tall, like a TV screen)" if wide else "VERTICAL 9:16 FRAME (taller than wide, like a phone screen)")
        + ", with a thin black border. In the top-left corner of each panel put only its number in a small black box. No other text, "
        "no captions, no speech bubbles inside the panels. Small motion lines or a curved arrow are allowed when something moves."
        + (" In every panel all characters and the action stay inside the CENTRAL THIRD of the panel width." if wide else ""),
        "CHARACTERS: LUNA = little astronaut girl, round glass helmet with ear pods, two hair buns, one-piece astronaut jumpsuit with round "
        "chest button, knee pads, small backpack. LEO = her little brother, same suit, hair tuft sticking out of the top of the helmet, "
        "slightly shorter than Luna. STELLINA = one small cute five-pointed star with very rounded points, big eyes and a smile, NO arms, "
        "NO legs, always floating, with a few short glow lines. Only ONE Stellina. Helmets always on. "
        f"In this episode: {', '.join(c.capitalize() for c in E['cast'])}.",
        "SET: " + P["m"].SETS[E["world"]].format(img="the set image").replace("use the set image as the background:", "Mars like the set image:")
        + " Sketched lightly in pencil.",
        "PROPS: " + re.sub(r"\{[a-z_]+\}", "the prop image", E.get("props_text", "")).replace("SOLID opaque colors", "clearly different shapes")
        if E.get("props_text") else "",
        "FRAMING (identical in all panels, " + ("static camera" if not E.get("camera") else "camera: " + E["camera"]) +
        ", at the children's eye level): " + re.sub(r"^FRAMING:\s*", "", E.get("framing", "")),
        "\n".join(f"PANEL {i} ({s['t0']:g}-{s['t1']:g}s): {s['text']}" for i, s in enumerate(P["shots"], 1)),
        ("The last panel ends exactly like panel 1 (same positions and poses), so the video loops." if not E.get("no_loop") else ""),
        (f"CORRECTION: the LAST attached image is the previous version of this sheet. Keep every panel identical and redraw ONLY panel "
         f"{redo_panel}" + (f": {note}" if note else ".")) if redo_panel else (f"DIRECTOR'S NOTE: {note}" if note else ""),
    ]
    return "\n\n".join(l for l in lines if l)


def _openai_sheet(prompt, files, wide, log):
    if not config.OPENAI_API_KEY: raise RuntimeError("OPENAI_API_KEY non impostata")
    size = "1024x1536" if wide else "1536x1024"
    data = {"model": OPENAI_IMAGE_MODEL, "prompt": prompt[:30000], "size": size, "quality": OPENAI_IMAGE_QUALITY, "n": "1"}
    fh = [("image[]", (f.name, open(f, "rb"), "image/png")) for f in files]
    log(f"OpenAI {OPENAI_IMAGE_MODEL}: tavola {size}, {len(files)} riferimenti")
    try:
        r = requests.post("https://api.openai.com/v1/images/edits", headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                          data=data, files=fh, timeout=600)
    finally:
        for _, (_, h, _) in fh: h.close()
    if r.status_code >= 300: raise RuntimeError(f"OpenAI immagini {r.status_code}: {r.text[:400]}")
    j = r.json(); import base64
    return base64.b64decode(j["data"][0]["b64_json"]), j.get("usage", {})


def _local_refs(P, d: Path):
    out = []
    for k, p in P["refs"]:
        f = d / "refs" / p.replace("/", "__")
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True); kie.download(_ref_url(p), f)
        out.append(f)
    return out


def info_sheet(P, sheet_img: Path, caps, out: Path, ep):
    """Tavola per Simone: il disegno così com'è + una fascia sotto con tempi, camera, azione in italiano e colori."""
    E = P["E"]; im = Image.open(sheet_img).convert("RGB")
    W = max(im.width, 1500); scale = W / im.width; im = im.resize((W, int(im.height * scale)))
    n = len(P["shots"]); cols = 3 if n > 4 else max(1, n); rows = (n + cols - 1) // cols
    head, row_h, pad = 120, 230, 36
    out_img = Image.new("RGB", (W, head + im.height + rows * row_h + pad), "white"); d = ImageDraw.Draw(out_img)
    props = E.get("props", [])
    d.text((pad, 22), f"{ep} · {E['title']}", font=_font(38, True), fill="black")
    d.text((pad, 74), f"Durata {E['duration']} s · {P['aspect']} · set {E['world']} · cast: {', '.join(E['cast'])}"
           + (f" · prop: {', '.join(props)}" if props else "") + " · camera: " + ("fissa" if not E.get("camera") else "come da prompt"),
           font=_font(22), fill=(60, 60, 60))
    out_img.paste(im, (0, head))
    cw = (W - 2 * pad) // cols; y0 = head + im.height + 16
    for i, (sh, cp) in enumerate(zip(P["shots"], caps)):
        r, c = divmod(i, cols); x = pad + c * cw; y = y0 + r * row_h
        d.text((x, y), f"{i + 1} · {sh['t0']:g}–{sh['t1']:g} s" + (f" · {cp['titolo']}" if cp.get("titolo") else ""), font=_font(22, True), fill="black")
        cx, yy = x, y + 32
        for name, rgb in _colors_in(sh["text"]):
            d.ellipse((cx, yy, cx + 22, yy + 22), fill=rgb, outline="black")
            d.text((cx + 28, yy), name, font=_font(18), fill="black"); cx += 40 + int(d.textlength(name, font=_font(18)))
        if cx > x: yy += 30
        d.text((x, yy), f"Camera: {cp.get('camera') or 'fissa'}", font=_font(18), fill=(70, 70, 70)); yy += 26
        for line in textwrap.wrap(cp.get("azione") or sh["text"], int(cw / 10))[:5]:
            d.text((x, yy), line, font=_font(18), fill="black"); yy += 24
        if i == n - 1 and not E.get("no_loop"):
            d.text((x, yy + 2), "↺ loop: finisce come il pannello 1", font=_font(18, True), fill=(40, 110, 230))
    out_img.save(out, optimize=True)
    return out


def _finish(ep, P, sb, ver, raw: Path, d: Path, cost, source, log):
    caps, cap_cost = captions(P)
    if cap_cost: costs.record(episodio=ep, tipo="didascalie storyboard", servizio="openai", modello=config.OPENAI_IDEAS_MODEL, costo_usd=cap_cost, esito="ok")
    sheet = info_sheet(P, raw, caps, d / f"{ep}_storyboard_v{ver:02d}.png", ep)
    pre = f"{config.SUPABASE_VIDEO_PREFIX}/{config.CHANNEL}/{ep}/storyboard"
    sheet_url = storage.upload(sheet, f"{pre}/{sheet.name}"); raw_url = storage.upload(raw, f"{pre}/{raw.name}")
    panels = [{"id": s["id"], "t0": s["t0"], "t1": s["t1"]} for s in P["shots"]]
    return {"version": ver, "approved": False, "source": source, "sheet": sheet.name, "sheet_url": sheet_url,
            "strip": raw.name, "strip_url": raw_url, "panels": panels, "captions": caps, "cost_usd": cost,
            "created": time.strftime("%Y-%m-%dT%H:%M:%S")}


def generate_openai(ep, ep_dir: Path, st: dict, log, only=None, note=""):
    P = plan(ep)
    if P["missing"]:
        raise RuntimeError("Mancano su Supabase: " + ", ".join(P["missing"]) +
                           (f"  (carica lo sheet a matita come {STYLE_REF})" if STYLE_REF in P["missing"] else ""))
    sb = dict(st.get("storyboard") or {}); ver = int(sb.get("version", 0)) + 1; n = len(P["shots"])
    d = ep_dir / "storyboard"; d.mkdir(parents=True, exist_ok=True)
    files = _local_refs(P, d)
    if only:
        if not 1 <= only <= n: raise RuntimeError(f"{ep} ha {n} pannelli: scegli tra 1 e {n}")
        old = d / sb.get("strip", "")
        if not sb or not old.is_file(): raise RuntimeError(f"{ep}: nessuno storyboard da correggere, lancia prima /storyboard {ep}")
        files = files + [old]
    png, usage = _openai_sheet(sheet_prompt(P, note, only), files, P["wide"], log)
    raw = d / f"{ep}_storyboard_v{ver:02d}_seedance.png"; raw.write_bytes(png)
    costs.record(episodio=ep, tipo=f"storyboard v{ver}" + (f" (pannello {only})" if only else ""), servizio="openai",
                 modello=OPENAI_IMAGE_MODEL, risoluzione="1536x1024", costo_usd=OPENAI_IMAGE_COST, esito="stima",
                 note=json.dumps(usage))
    return _finish(ep, P, sb, ver, raw, d, OPENAI_IMAGE_COST, "openai", log)


def from_upload(ep, ep_dir: Path, st: dict, image: Path, log):
    """Storyboard fatto a mano (es. in ChatGPT) e mandato al bot come foto: diventa la versione da approvare."""
    P = plan(ep); sb = dict(st.get("storyboard") or {}); ver = int(sb.get("version", 0)) + 1
    d = ep_dir / "storyboard"; d.mkdir(parents=True, exist_ok=True)
    raw = d / f"{ep}_storyboard_v{ver:02d}_seedance.png"
    Image.open(image).convert("RGB").save(raw)
    return _finish(ep, P, sb, ver, raw, d, None, "caricato", log)


def generate(ep, ep_dir: Path, st: dict, log, only=None, note=""):
    if PROVIDER == "kie": return generate_kie(ep, ep_dir, st, log, only=only, note=note)
    return generate_openai(ep, ep_dir, st, log, only=only, note=note)
