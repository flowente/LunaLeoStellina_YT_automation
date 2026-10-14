"""Configurazione dal solo ambiente (variabili di Railway). Nessuna chiave nel codice."""
import os
from pathlib import Path

def env(name, default=None, required=False):
    v = os.environ.get(name)
    if v is not None:
        v = v.split(" #")[0].split("\t#")[0].strip().strip("`'\"")    # toglie commenti incollati per errore, spazi e virgolette
        if v.startswith("#"): v = ""
    if not v: v = default
    if required and not v:
        raise RuntimeError(f"Variabile d'ambiente mancante: {name}")
    return v

def _num(v):
    try: return float(str(v).replace(",", "."))
    except (TypeError, ValueError): return 0.0

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
OPENAI_PRICE_IN = _num(env("OPENAI_PRICE_IN_PER_M", "0"))    # $ per 1M token in ingresso (per il registro costi)
OPENAI_PRICE_OUT = _num(env("OPENAI_PRICE_OUT_PER_M", "0"))

# Supabase Storage (link pubblici per Buffer e per n8n)
SUPABASE_URL = env("SUPABASE_URL", "https://nerfwrxouzqrabtjszbp.supabase.co")
SUPABASE_KEY = env("SUPABASE_SERVICE_KEY", "")
SUPABASE_REFS_BUCKET = env("SUPABASE_REFS_BUCKET", "youtube_short")       # tavole personaggi e mondi (già esistente)
SUPABASE_VIDEO_BUCKET = env("SUPABASE_VIDEO_BUCKET", "youtube_short")     # bucket PUBBLICO (lo stesso delle tavole)
SUPABASE_VIDEO_PREFIX = env("SUPABASE_VIDEO_PREFIX", "video")              # cartella dei video nel bucket

# Buffer
BUFFER_API_KEY = env("BUFFER_API_KEY", "")
BUFFER_API_URL = env("BUFFER_API_URL", "https://api.buffer.com")

# Upscale del finale. "Approva" usa:
#   UPSCALE_PROVIDER=seedance -> come prima: Seedance rigenera la take a 1080p (≈ $0,79/s)
#   UPSCALE_PROVIDER=fal      -> la bozza 480p approvata passa da SeedVR2 su fal.ai (≈ $0,001 per megapixel)
# Il comando /upscale usa sempre fal (per provare la strada nuova senza toccare "Approva").
UPSCALE_PROVIDER = (env("UPSCALE_PROVIDER", "seedance") or "seedance").lower()
FAL_KEY = env("FAL_KEY", "")
FAL_UPSCALE_MODEL = env("FAL_UPSCALE_MODEL", "fal-ai/seedvr/upscale/video")
FAL_UPSCALE_TARGET = env("FAL_UPSCALE_TARGET", "1080p")
FAL_UPSCALE_NOISE = _num(env("FAL_UPSCALE_NOISE", "0.05"))
FAL_UPSCALE_SEED = int(_num(env("FAL_UPSCALE_SEED", "42")))
FAL_PRICE_PER_MP = _num(env("FAL_PRICE_PER_MP", "0.001"))
# Correzione applicata al video upscalato PRIMA del color grade del canale (tarata su EP028, 14/10/2026):
#   il 480p di Seedance nasce più saturo del 1080p (+9%) -> saturazione 0,86;
#   il dettaglio ricostruito "brulica" tra i fotogrammi -> leggero filtro temporale (hqdn3d, solo tempo).
UPSCALE_FIX_VF = env("UPSCALE_FIX_VF", "eq=saturation=0.86,hqdn3d=0:0:4:4")

# n8n: dove il servizio avvisa quando un lavoro finisce (report bozza, finale pronto, post programmato)
N8N_WEBHOOK_URL = env("N8N_WEBHOOK_URL", "")

CHANNEL = env("CHANNEL", "lunaleo")
APP = Path(__file__).resolve().parent
FONTS = APP / "fonts"
