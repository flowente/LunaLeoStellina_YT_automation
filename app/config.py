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
# Listino OpenAI, $ per 1M token, tier Standard (developers.openai.com/api/docs/pricing, letto il 15/10/2026).
# Le variabili OPENAI_PRICE_*_PER_M su Railway, se impostate, hanno la precedenza.
OPENAI_PRICES = {
    "gpt-6-astra":  {"in": 10.00, "cached": 1.00, "out": 50.00},
    "gpt-6.1-sol":  {"in": 2.00,  "cached": 0.10, "out": 10.00},
    "gpt-6-luna":   {"in": 0.10,  "cached": 0.01, "out": 0.50},
}
_p = OPENAI_PRICES.get(OPENAI_MODEL, {})
OPENAI_PRICE_IN = _num(env("OPENAI_PRICE_IN_PER_M", str(_p.get("in", 0))))
OPENAI_PRICE_CACHED = _num(env("OPENAI_PRICE_CACHED_PER_M", str(_p.get("cached", _p.get("in", 0)))))
OPENAI_PRICE_OUT = _num(env("OPENAI_PRICE_OUT_PER_M", str(_p.get("out", 0))))


# Modello per /idee e /brainstorming: testi brevi, nessun rischio di spesa -> modello economico (5 volte meno di astra).
# Giudice e scrittura dell'episodio finale (/nuovo, /modifica) restano su OPENAI_MODEL: un prompt sbagliato costa una bozza.
OPENAI_IDEAS_MODEL = env("OPENAI_IDEAS_MODEL", "gpt-6.1-sol")


def openai_cost(usage: dict, model: str = None) -> float:
    """Costo di una chiamata dai token restituiti da OpenAI (i token in cache costano meno)."""
    if model and model != OPENAI_MODEL and model in OPENAI_PRICES:
        p = OPENAI_PRICES[model]; pin, pc, pout = p["in"], p["cached"], p["out"]
    else:
        pin, pc, pout = OPENAI_PRICE_IN, OPENAI_PRICE_CACHED, OPENAI_PRICE_OUT
    inp = usage.get("input_tokens", 0) or 0
    cached = (usage.get("input_tokens_details") or {}).get("cached_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    return round(((inp - cached) * pin + cached * pc + out * pout) / 1e6, 4)

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
