"""Configurazione dal solo ambiente (variabili di Railway). Nessuna chiave nel codice."""
import os
from pathlib import Path

def env(name, default=None, required=False):
    v = os.environ.get(name, default)
    if required and not v:
        raise RuntimeError(f"Variabile d'ambiente mancante: {name}")
    return v

# Sicurezza del servizio: ogni chiamata deve avere l'header  X-Token: <SERVICE_TOKEN>
SERVICE_TOKEN = env("SERVICE_TOKEN", "")

# Dati persistenti (volume Railway montato qui): video, stato degli episodi, registro costi
DATA = Path(env("DATA_DIR", "/data"))

# Kie AI (Seedance)
KIE_API_KEY = env("KIE_API_KEY", "")
KIE_API = "https://api.kie.ai"
KIE_CREDIT_USD = 0.005

# OpenAI (giudice visivo)
OPENAI_API_KEY = env("OPENAI_API_KEY", "")
OPENAI_MODEL = env("OPENAI_VISION_MODEL", "gpt-6-astra")
OPENAI_PRICE_IN = float(env("OPENAI_PRICE_IN_PER_M", "0") or 0)    # $ per 1M token in ingresso (per il registro costi)
OPENAI_PRICE_OUT = float(env("OPENAI_PRICE_OUT_PER_M", "0") or 0)

# Supabase Storage (link pubblici per Buffer e per n8n)
SUPABASE_URL = env("SUPABASE_URL", "https://nerfwrxouzqrabtjszbp.supabase.co")
SUPABASE_KEY = env("SUPABASE_SERVICE_KEY", "")
SUPABASE_REFS_BUCKET = env("SUPABASE_REFS_BUCKET", "youtube_short")       # tavole personaggi e mondi (già esistente)
SUPABASE_VIDEO_BUCKET = env("SUPABASE_VIDEO_BUCKET", "yt_videos")         # bucket PUBBLICO per i video da programmare

# Buffer
BUFFER_API_KEY = env("BUFFER_API_KEY", "")
BUFFER_API_URL = env("BUFFER_API_URL", "https://api.buffer.com")

# n8n: dove il servizio avvisa quando un lavoro finisce (report bozza, finale pronto, post programmato)
N8N_WEBHOOK_URL = env("N8N_WEBHOOK_URL", "")

CHANNEL = env("CHANNEL", "lunaleo")
APP = Path(__file__).resolve().parent
FONTS = APP / "fonts"
