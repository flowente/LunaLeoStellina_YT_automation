"""Upscale del finale con SeedVR2 su fal.ai: bozza 480p approvata -> 1080x1920, al posto della rigenerazione 1080p di Seedance.

Uso: il servizio carica la bozza GREZZA su Supabase (fal vuole un link pubblico), la manda alla coda di fal,
aspetta, scarica il risultato, lo porta esattamente a 1080x1920 con la correzione UPSCALE_FIX_VF
e rimette l'audio originale della bozza. Il color grade del canale lo applica poi postprod.finalize, come sempre.
"""
import json, subprocess, time
from pathlib import Path
import requests
from . import config, postprod

QUEUE = "https://queue.fal.run"
H = lambda: {"Authorization": f"Key {config.FAL_KEY}", "Content-Type": "application/json"}


def enabled():
    return bool(config.FAL_KEY)


def submit(video_url: str) -> dict:
    """Mette il lavoro in coda. Restituisce request_id, status_url e response_url (da salvare per la ripresa)."""
    if not config.FAL_KEY: raise RuntimeError("FAL_KEY non impostata nelle variabili di Railway")
    body = {"video_url": video_url, "upscale_mode": "target", "target_resolution": config.FAL_UPSCALE_TARGET,
            "noise_scale": config.FAL_UPSCALE_NOISE, "seed": config.FAL_UPSCALE_SEED,
            "output_format": "X264 (.mp4)", "output_quality": "high", "output_write_mode": "balanced"}
    r = requests.post(f"{QUEUE}/{config.FAL_UPSCALE_MODEL}", headers=H(), json=body, timeout=60)
    if r.status_code >= 300: raise RuntimeError(f"fal {r.status_code}: {r.text[:300]}")
    j = r.json()
    return {"request_id": j["request_id"], "status_url": j["status_url"], "response_url": j["response_url"]}


def wait(job: dict, timeout_s=30 * 60, log=print) -> dict:
    t0, w = time.time(), 10
    while True:
        time.sleep(w); w = min(w + 5, 30)
        r = requests.get(job["status_url"], headers=H(), timeout=60)
        st = (r.json() if r.ok else {}).get("status", f"HTTP {r.status_code}")
        log(f"fal {int(time.time() - t0)}s · {st}")
        if st == "COMPLETED": break
        if time.time() - t0 > timeout_s: raise TimeoutError(f"fal: richiesta {job['request_id']} ancora in corso")
    r = requests.get(job["response_url"], headers=H(), timeout=60)
    res = r.json() if r.ok else {}
    if not (res.get("video") or {}).get("url"):
        raise RuntimeError(f"fal: upscale fallito ({r.status_code}): {r.text[:300]}")
    return res


def probe(video: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
                          "-show_entries", "stream=width,height,nb_read_packets", "-of", "json", str(video)],
                         capture_output=True, text=True).stdout
    s = json.loads(out)["streams"][0]
    return {"w": int(s["width"]), "h": int(s["height"]), "frames": int(s.get("nb_read_packets") or 0)}


def cost_usd(video: Path) -> tuple:
    p = probe(video); mp = p["w"] * p["h"] * p["frames"] / 1e6
    return round(mp * config.FAL_PRICE_PER_MP, 3), p


def conform(upscaled: Path, draft_raw: Path, out: Path) -> Path:
    """Esattamente 1080x1920 + correzione colore/tremolio + audio originale della bozza."""
    vf = "scale=1080:1920:flags=lanczos" + ("," + config.UPSCALE_FIX_VF if config.UPSCALE_FIX_VF else "") + ",setsar=1"
    subprocess.run([postprod.ffmpeg(), "-v", "error", "-y", "-i", str(upscaled), "-i", str(draft_raw),
                    "-map", "0:v:0", "-map", "1:a:0?", "-vf", vf,
                    "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p",
                    "-c:a", "copy", str(out)], check=True)
    return out


def download(url: str, path: Path) -> Path:
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20): f.write(chunk)
    return path
