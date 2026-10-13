"""Supabase Storage: link pubblici per Buffer (che vuole un URL diretto) e per n8n (che salva la copia su Drive/PC).
I file restano solo fino alla pubblicazione, poi si cancellano (POST /episodes/{ep}/cleanup) per non riempire lo spazio."""
import mimetypes
from pathlib import Path
import requests
from . import config


def _h(extra=None):
    h = {"Authorization": f"Bearer {config.SUPABASE_KEY}", "apikey": config.SUPABASE_KEY}
    h.update(extra or {}); return h


def public_url(path: str) -> str:
    return f"{config.SUPABASE_URL}/storage/v1/object/public/{config.SUPABASE_VIDEO_BUCKET}/{path}"


def upload(local: Path, path: str) -> str:
    if not config.SUPABASE_KEY: raise RuntimeError("SUPABASE_SERVICE_KEY non impostata")
    ct = mimetypes.guess_type(str(local))[0] or "application/octet-stream"
    with open(local, "rb") as f:
        r = requests.post(f"{config.SUPABASE_URL}/storage/v1/object/{config.SUPABASE_VIDEO_BUCKET}/{path}",
                          headers=_h({"Content-Type": ct, "x-upsert": "true", "cache-control": "3600"}), data=f, timeout=600)
    if r.status_code >= 300: raise RuntimeError(f"Supabase upload {r.status_code}: {r.text[:300]}")
    return public_url(path)


def delete(paths):
    r = requests.delete(f"{config.SUPABASE_URL}/storage/v1/object/{config.SUPABASE_VIDEO_BUCKET}",
                        headers=_h({"Content-Type": "application/json"}), json={"prefixes": list(paths)}, timeout=60)
    if r.status_code >= 300: raise RuntimeError(f"Supabase delete {r.status_code}: {r.text[:300]}")
    return r.json()
