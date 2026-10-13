#!/usr/bin/env python3
"""
Controllore video v0 — Luna, Leo e Stellina.

Analizza una bozza (o un finale) e produce un report per shot:
  - SHOT: i blocchi di tempo del prompt (0-2s, 2-5s, ...) letti da v3/eps.py -> EPxxx_S01, S02, ...
  - FOTOGRAMMA CHIAVE di ogni shot: il momento più fermo nella seconda metà dello shot (posa leggibile)
  - COMPOSIZIONE (solo fotogrammi chiave + media sullo shot): altezza dei personaggi in % del fotogramma,
    posizione dei piedi, dimensione di Stellina — confrontate con canon.json
  - COERENZA (tutti i fotogrammi campionati): numero di Stellina, salti/teletrasporti, camera che zooma o deriva
  - LOOP: somiglianza primo/ultimo fotogramma
  - Griglia di fotogrammi per shot (per il controllo artistico)

Uso:
  python qc.py <video.mp4> [--ep EP010] [--out cartella]
"""
import argparse, json, os, re, sys
from pathlib import Path
import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
CANON = HERE / "channels" / os.environ.get("CHANNEL", "lunaleo") / "canon.json"
FPS_SAMPLE = 8                             # fotogrammi analizzati al secondo

# ------------------------------------------------------------------ shot dal prompt
def shots_for(ep_id, duration):
    try:
        from . import episodes
        _, eps = episodes.all_episodes()
        out = [dict(id=f"{ep_id}_{x['id']}", t0=x["t0"], t1=min(x["t1"], duration), text=x["text"]) for x in episodes.shots(eps[ep_id])]
        if out: return out
    except Exception as e:
        print("  (shot dal prompt non disponibili:", e, ")")
    n = max(1, round(duration / 3))
    return [dict(id=f"{ep_id}_S{i+1:02d}", t0=i * duration / n, t1=(i + 1) * duration / n, text="") for i in range(n)]

# ------------------------------------------------------------------ rilevamento personaggi
_yolo = None
def yolo():
    global _yolo
    if _yolo is None:
        import os
        if os.environ.get("QC_YOLO") != "1":      # v0: il YOLO generico non riconosce bene i bambini cartoon -> spento finché non addestriamo il nostro
            _yolo = False; return _yolo
        try:
            from ultralytics import YOLO
            w = HERE / "models" / "yolo11n.pt"
            _yolo = YOLO(str(w) if w.exists() else "yolo11n.pt")
        except Exception as e:
            print("  YOLO non disponibile:", e); _yolo = False
    return _yolo

# colori firma (HSV OpenCV: H 0-180)
def hsv_mask(hsv, lo, hi):
    return cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))

def name_child(crop_hsv):
    """Luna = accenti corallo/rossi, Leo = accenti verde menta/acqua."""
    coral = hsv_mask(crop_hsv, (0, 90, 120), (8, 255, 255)) | hsv_mask(crop_hsv, (170, 90, 120), (180, 255, 255))
    mint = hsv_mask(crop_hsv, (70, 50, 110), (95, 255, 255))
    c, m = int(coral.sum() // 255), int(mint.sum() // 255)
    if max(c, m) < 30: return "bambino?"
    return "Luna" if c > m else "Leo"

def find_stellina(hsv, H, W):
    """Blob giallo luminoso (Stellina, ma anche oggetti gialli: vengono contati tutti come 'gialli brillanti')."""
    m = hsv_mask(hsv, (20, 70, 200), (34, 255, 255))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    blobs = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a > 0.004 * H * W and 0.5 < w / max(h, 1) < 2.0:
            blobs.append(dict(x=x / W, y=y / H, w=w / W, h=h / H, area=a / (H * W)))
    return sorted(blobs, key=lambda b: -b["area"])

_seg = None
def seg_session():
    """Segmentazione personaggi con isnet-anime (rembg): funziona bene sui personaggi cartoon, gira su CPU."""
    global _seg
    if _seg is None:
        try:
            from rembg import new_session
            _seg = new_session("isnet-anime")
        except Exception as e:
            print("  segmentazione non disponibile:", e); _seg = False
    return _seg

def detect_kids(frame, hsv):
    ses = seg_session()
    if not ses: return []
    from rembg import remove
    from PIL import Image
    H, W = frame.shape[:2]
    m = np.array(remove(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), session=ses, only_mask=True))
    m = (m > 200).astype(np.uint8) * 255
    yel = hsv_mask(hsv, (18, 60, 190), (36, 255, 255))           # Stellina e luci gialle: non sono bambini
    m[yel > 0] = 0
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    kids = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if h < 0.12 * H or a < 0.012 * H * W: continue
        if x == 0 and w < 0.25 * W and (a / (w * h)) > 0.7: continue      # razzo tagliato dal bordo
        px = hsv[lab == i]
        coral = ((px[:, 0] <= 8) | (px[:, 0] >= 170)) & (px[:, 1] > 90) & (px[:, 2] > 120)
        mint = (px[:, 0] >= 70) & (px[:, 0] <= 95) & (px[:, 1] > 50) & (px[:, 2] > 110)
        white = (px[:, 1] < 50) & (px[:, 2] > 170)
        if white.mean() < 0.15: continue                                   # non è un astronauta (sasso, rover...)
        c, mi = int(coral.sum()), int(mint.sum())
        name = "Luna" if c > mi * 1.2 else ("Leo" if mi > c * 1.2 else "bambino?")
        kids.append(dict(name=name, x=(x + w / 2) / W, top=y / H, feet=1 - (y + h) / H, h=h / H, w=w / W, coral=c, mint=mi))
    if len(kids) == 2 and kids[0]["name"] == kids[1]["name"]:
        a_, b_ = kids
        if (a_["coral"] - a_["mint"]) >= (b_["coral"] - b_["mint"]): a_["name"], b_["name"] = "Luna", "Leo"
        else: a_["name"], b_["name"] = "Leo", "Luna"
    return kids

def detect(frame, kids=True):
    H, W = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    return dict(kids=detect_kids(frame, hsv) if kids else [], yellow=find_stellina(hsv, H, W))

# ------------------------------------------------------------------ movimento e camera
def global_motion(prev_g, g):
    """Scala e traslazione della camera tra due fotogrammi, usando SOLO lo sfondo fermo
    (i personaggi che si muovono vengono esclusi, altrimenti sembrano zoom)."""
    still = (cv2.absdiff(prev_g, g) < 6).astype(np.uint8) * 255
    still = cv2.erode(still, np.ones((9, 9), np.uint8))
    orb = cv2.ORB_create(800)
    k1, d1 = orb.detectAndCompute(prev_g, still); k2, d2 = orb.detectAndCompute(g, None)
    if d1 is None or d2 is None or len(k1) < 25 or len(k2) < 25: return 1.0, 0.0
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    ms = sorted(bf.match(d1, d2), key=lambda m: m.distance)[:200]
    if len(ms) < 20: return 1.0, 0.0
    p1 = np.float32([k1[m.queryIdx].pt for m in ms]); p2 = np.float32([k2[m.trainIdx].pt for m in ms])
    M, inl = cv2.estimateAffinePartial2D(p1, p2, method=cv2.RANSAC, ransacReprojThreshold=2)
    if M is None or inl is None or inl.sum() < 20: return 1.0, 0.0
    s = float(np.sqrt(M[0, 0] ** 2 + M[0, 1] ** 2))
    if abs(s - 1) > 0.08: return 1.0, 0.0          # salto non plausibile per una camera: rumore
    return s, float(np.hypot(M[0, 2], M[1, 2]) / g.shape[1])

def ssim_gray(a, b):
    a = a.astype(np.float64); b = b.astype(np.float64)
    c1, c2 = 6.5025, 58.5225
    mu_a = cv2.GaussianBlur(a, (11, 11), 1.5); mu_b = cv2.GaussianBlur(b, (11, 11), 1.5)
    sa = cv2.GaussianBlur(a * a, (11, 11), 1.5) - mu_a ** 2; sb = cv2.GaussianBlur(b * b, (11, 11), 1.5) - mu_b ** 2
    sab = cv2.GaussianBlur(a * b, (11, 11), 1.5) - mu_a * mu_b
    return float((((2 * mu_a * mu_b + c1) * (2 * sab + c2)) / ((mu_a ** 2 + mu_b ** 2 + c1) * (sa + sb + c2))).mean())


def spin_snaps(video):
    """Scatti nelle giravolte: il movimento orizzontale del corpo si inverte di colpo (es. EP007 take 1, Luna a 6,1 s).
    Flusso ottico a piena frequenza, separatamente nella metà sinistra e destra del fotogramma."""
    c = cv2.VideoCapture(str(video)); fps = c.get(cv2.CAP_PROP_FPS) or 24
    prev, xs, t = None, [], 0
    while True:
        ok, f = c.read()
        if not ok: break
        g = cv2.cvtColor(cv2.resize(f, (240, 427)), cv2.COLOR_BGR2GRAY)
        if prev is not None:
            fl = cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            mag = np.hypot(fl[..., 0], fl[..., 1]); row = []
            for x0, x1 in ((0, 120), (120, 240)):
                sub = fl[150:400, x0:x1]; m = mag[150:400, x0:x1] > 1.0
                row.append(float(np.median(sub[..., 0][m])) if m.sum() > 200 else 0.0)
            xs.append((t / fps, row))
        prev = g; t += 1
    ev = []
    for side, nome in ((0, "sinistra"), (1, "destra")):
        for i in range(3, len(xs)):
            a, b = xs[i - 3][1][side], xs[i][1][side]
            if np.sign(a) != np.sign(b) and min(abs(a), abs(b)) >= 2.0 and max(abs(a), abs(b)) >= 3.0:
                if not ev or ev[-1][1] != nome or xs[i][0] - ev[-1][0] > 0.5:
                    ev.append((round(xs[i][0], 2), nome))
    return ev

# ------------------------------------------------------------------ analisi
def load_frames(video):
    cap = cv2.VideoCapture(str(video)); fps = cap.get(cv2.CAP_PROP_FPS) or 24
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); step = max(1, round(fps / FPS_SAMPLE))
    frames, times, i = [], [], 0
    while True:
        ok, f = cap.read()
        if not ok: break
        if i % step == 0:
            h, w = f.shape[:2]
            if h > 960: f = cv2.resize(f, (w * 960 // h, 960))
            frames.append(f); times.append(i / fps)
        i += 1
    last = None
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, n - 1)); ok, last = cap.read()
    if ok and last.shape[0] > 960: last = cv2.resize(last, (last.shape[1] * 960 // last.shape[0], 960))
    return frames, times, n / fps, (last if ok else frames[-1])

def analyze(video, ep_id=None, out=None):
    video = Path(video)
    ep_id = ep_id or re.match(r"(EP\d+)", video.name)[1]
    canon = json.loads(CANON.read_text(encoding="utf-8")) if CANON.exists() else {}
    frames, times, dur, last = load_frames(video)
    H, W = frames[0].shape[:2]
    grays = [cv2.cvtColor(cv2.resize(f, (W // 2, H // 2)), cv2.COLOR_BGR2GRAY) for f in frames]

    # movimento per fotogramma (quanto cambia l'immagine) e camera
    motion = [0.0] + [float(cv2.absdiff(grays[i], grays[i - 1]).mean()) for i in range(1, len(grays))]
    cam = [(1.0, 0.0)] + [global_motion(grays[i - 1], grays[i]) for i in range(1, len(grays))]
    det = [detect(f, kids=False) for f in frames]

    shots = shots_for(ep_id, dur)
    report = dict(video=video.name, episode=ep_id, duration=round(dur, 2), resolution=f"{W}x{H}", shots=[], global_issues=[])

    # --- camera: zoom cumulativo e deriva (solo se la camera è dichiarata ferma)
    zoom = float(np.prod([c[0] for c in cam])); drift = float(sum(c[1] for c in cam))
    report["camera"] = dict(zoom_totale=round(zoom, 3), deriva=round(drift, 3))
    lim = canon.get("camera_ferma", {"zoom_max": 0.06, "deriva_max": 0.15})
    if abs(zoom - 1) > lim["zoom_max"]:
        report["global_issues"].append(f"CAMERA: zoom complessivo {100*(zoom-1):+.0f}% (camera dichiarata ferma: massimo ±{100*lim['zoom_max']:.0f}%)")
    # zoom iniziale (il difetto classico: parte larga e si avvicina)
    k = min(len(cam), FPS_SAMPLE * 2)
    z0 = float(np.prod([c[0] for c in cam[:k]]))
    if abs(z0 - 1) > lim["zoom_max"] / 2:
        report["global_issues"].append(f"CAMERA: nei primi 2 s l'inquadratura cambia scala del {100*(z0-1):+.0f}% (deve essere già quella finale dal primo fotogramma)")

    # --- scatti / teletrasporti: picchi isolati di cambiamento rispetto ai vicini
    mv = np.array(motion)
    for i in range(2, len(mv) - 2):
        neigh = np.median(np.r_[mv[i - 2:i], mv[i + 1:i + 3]])
        if mv[i] > max(9.0, 4.0 * neigh) and times[i] > 0.3:
            report["global_issues"].append(f"SCATTO: cambiamento improvviso a {times[i]:.2f}s (x{mv[i]/max(neigh,0.1):.1f} rispetto ai fotogrammi vicini)")

    # --- scatti nelle giravolte (inversione di direzione)
    spin_shots = [s_ for s_ in shots if re.search(r"(Luna|Leo|children|they|each)[^.;]*\b(spins?|twirls?|turns?|rotat\w*|pirouette)", s_["text"], re.I)]
    for t_, side in spin_snaps(video):
        if not any(s_["t0"] - 0.3 <= t_ <= s_["t1"] + 0.3 for s_ in spin_shots): continue   # solo dove la sceneggiatura prevede una giravolta
        report["global_issues"].append(f"SCATTO DI ROTAZIONE: a {t_:.2f}s il movimento nella metà {side} del quadro si inverte di colpo (giravolta che cambia verso)")

    # --- loop
    g0 = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY); gl = cv2.cvtColor(cv2.resize(last, (W, H)), cv2.COLOR_BGR2GRAY)
    loop = ssim_gray(g0, gl)
    report["loop"] = dict(somiglianza_primo_ultimo=round(loop, 3), soglia=canon.get("loop_min", 0.6))
    if loop < canon.get("loop_min", 0.6):
        report["global_issues"].append(f"LOOP: primo e ultimo fotogramma diversi (somiglianza {loop:.2f}, minimo {canon.get('loop_min',0.6)})")

    # --- per shot
    for s in shots:
        idx = [i for i, t in enumerate(times) if s["t0"] <= t < s["t1"]]
        if not idx: continue
        half = idx[len(idx) // 2:]
        kf = min(half, key=lambda i: motion[i])                      # momento più fermo nella 2a metà
        for i in sorted({idx[0], idx[len(idx) // 2], kf, idx[-1]}):   # bambini: 4 fotogrammi per shot
            det[i]["kids"] = detect(frames[i])["kids"]
        d = det[kf]
        kids = d["kids"]; yel = d["yellow"]
        names = sorted(k["name"] for k in kids)
        n_people = len(kids)
        # medie sullo shot
        hs = {}
        for i in idx:
            for k_ in det[i]["kids"]: hs.setdefault(k_["name"], []).append(k_["h"])
        mean_h = {k_: round(float(np.median(v)) * 100, 1) for k_, v in hs.items()}
        max_yellow = max((len(det[i]["yellow"]) for i in idx), default=0)
        shot = dict(id=s["id"], tempo=f"{s['t0']:g}-{s['t1']:g}s", azione=s["text"][:140], fotogramma_chiave=round(times[kf], 2),
                    personaggi_chiave=[dict(nome=k_["name"], altezza_pct=round(k_["h"] * 100, 1), piedi_pct=round(k_["feet"] * 100, 1), x_pct=round(k_["x"] * 100, 1)) for k_ in kids],
                    stellina_chiave=(dict(larghezza_pct=round(yel[0]["w"] * 100, 1), y_pct=round(yel[0]["y"] * 100, 1)) if yel else None),
                    altezza_mediana_shot=mean_h, gialli_brillanti_max=max_yellow, problemi=[], rifacimento=None)
        # confronto con il canone (per numero di bambini in scena)
        rule = canon.get("composizione", {}).get(str(n_people))
        if rule and kids:
            lo, hi = rule["altezza_pct"]
            for k_ in kids:
                h = k_["h"] * 100
                if not lo <= h <= hi:
                    shot["problemi"].append(f"{k_['name']}: altezza {h:.0f}% · richiesta {lo}-{hi}% ({rule['nome']})")
            for nm, mh in mean_h.items():
                if mh < lo * 0.85:
                    shot["problemi"].append(f"{nm}: troppo piccolo per tutto lo shot (mediana {mh:.0f}%, richiesta {lo}-{hi}%)")
        if yel and canon.get("stellina_larghezza_pct"):
            lo, hi = canon["stellina_larghezza_pct"]
            w = yel[0]["w"] * 100
            if not lo <= w <= hi:
                shot["problemi"].append(f"Stellina: larghezza {w:.0f}% · richiesta {lo}-{hi}%")
        if max_yellow > canon.get("gialli_max", 2):
            shot["problemi"].append(f"Possibili Stellina multiple: fino a {max_yellow} oggetti gialli brillanti nello stesso fotogramma")
        if shot["problemi"]:
            shot["rifacimento"] = dict(da_secondo=s["t0"], durata=round(s["t1"] - s["t0"], 1),
                                       costo_480p=round((s["t1"] - s["t0"]) * 0.14, 2),
                                       nota="ripartire dal fotogramma a %.1fs (first-frame) e rafforzare FRAMING/RULES con i valori richiesti" % s["t0"])
        report["shots"].append(shot)
        # griglia di fotogrammi dello shot
        if out:
            pick = idx[:: max(1, len(idx) // 4)][:4]
            if kf not in pick: pick = (pick + [kf])[-4:]
            tiles = []
            for i in sorted(set(pick)):
                t = cv2.resize(frames[i], (180, 320)); f = det[i]
                for k_ in f["kids"]:
                    x1 = int((k_["x"] - k_["w"] / 2) * 180); x2 = int((k_["x"] + k_["w"] / 2) * 180)
                    y1 = int(k_["top"] * 320); y2 = int((1 - k_["feet"]) * 320)
                    cv2.rectangle(t, (x1, y1), (x2, y2), (80, 80, 255) if k_["name"] == "Luna" else (160, 220, 60), 1)
                cv2.putText(t, f"{times[i]:.1f}s" + (" KEY" if i == kf else ""), (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
                tiles.append(t)
            cv2.imwrite(str(Path(out) / f"{video.stem}_{s['id']}.jpg"), np.hstack(tiles))

    n_prob = sum(len(s["problemi"]) for s in report["shots"]) + len(report["global_issues"])
    report["esito"] = "OK" if n_prob == 0 else f"{n_prob} segnalazioni"
    return report

def to_md(r):
    L = [f"# Controllo {r['video']} — {r['esito']}", f"Durata {r['duration']}s · {r['resolution']} · loop {r['loop']['somiglianza_primo_ultimo']} · camera zoom {r['camera']['zoom_totale']}", ""]
    for g in r["global_issues"]: L.append(f"- ⚠ {g}")
    for s in r["shots"]:
        L.append(f"\n## {s['id']} ({s['tempo']}) {'✓' if not s['problemi'] else '✗'}")
        L.append(f"Fotogramma chiave {s['fotogramma_chiave']}s · " + ", ".join(f"{p['nome']} {p['altezza_pct']}%" for p in s["personaggi_chiave"]) +
                 (f" · Stellina {s['stellina_chiave']['larghezza_pct']}% larghezza" if s["stellina_chiave"] else ""))
        for p in s["problemi"]: L.append(f"- ✗ {p}")
        if s["rifacimento"]: L.append(f"- → RIFACIMENTO: {s['rifacimento']['nota']} · ≈ ${s['rifacimento']['costo_480p']} in 480p")
    return "\n".join(L)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("--ep"); ap.add_argument("--out")
    a = ap.parse_args()
    out = Path(a.out or Path(a.video).parent / "qc"); out.mkdir(parents=True, exist_ok=True)
    r = analyze(a.video, a.ep, out)
    stem = Path(a.video).stem
    (out / f"{stem}_qc.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / f"{stem}_qc.md").write_text(to_md(r), encoding="utf-8")
    print(to_md(r))
