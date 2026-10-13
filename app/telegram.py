"""Bot Telegram: report delle bozze con i pulsanti Approva / Rifai / Programma, e comandi.

Comandi (solo dalla chat TELEGRAM_CHAT_ID):
  /bozza EP027      genera la bozza (con controllo)
  /stato EP027      stato dell'episodio
  /episodi          elenco episodi definiti
  /costi            totale spese registrate
  /id               mostra il tuo chat id (funziona sempre: serve per la configurazione)
"""
import json, os, requests
from . import config

TOKEN = config.env("TELEGRAM_BOT_TOKEN", "")
CHAT = config.env("TELEGRAM_CHAT_ID", "")
API = lambda m: f"https://api.telegram.org/bot{TOKEN}/{m}"


def enabled():
    return bool(TOKEN and CHAT)


def call(method, **payload):
    if not TOKEN: return None
    r = requests.post(API(method), json=payload, timeout=20)
    try: return r.json()
    except Exception: return None


def send(text, buttons=None, chat=None):
    p = {"chat_id": chat or CHAT, "text": text[:4000], "parse_mode": "HTML", "disable_web_page_preview": True}
    if buttons: p["reply_markup"] = {"inline_keyboard": buttons}
    return call("sendMessage", **p)


def send_video(url, caption, buttons=None):
    p = {"chat_id": CHAT, "video": url, "caption": caption[:1000], "parse_mode": "HTML", "supports_streaming": True}
    if buttons: p["reply_markup"] = {"inline_keyboard": buttons}
    res = call("sendVideo", **p)
    if not res or not res.get("ok"):          # se Telegram non riesce a scaricare il video, manda il link
        send(caption + f'\n\n<a href="{url}">▶️ Guarda la bozza</a>', buttons)
    return res


def set_webhook():
    dom = os.environ.get("RAILWAY_PUBLIC_DOMAIN") or os.environ.get("PUBLIC_DOMAIN")
    if not (TOKEN and dom): return None
    return call("setWebhook", url=f"https://{dom}/telegram/webhook", secret_token=_secret(),
                allowed_updates=["message", "callback_query"])


def _secret():
    import hashlib
    return hashlib.sha256(("tg" + config.SERVICE_TOKEN).encode()).hexdigest()[:48]


def check_secret(header):
    return header == _secret()


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def draft_report(out):
    v = out.get("verdict") or {}
    lines = [f"🎬 <b>{out['episode']}</b> · bozza take {out['take']}",
             f"Giudizio: <b>{esc(v.get('verdetto', 'non disponibile'))}</b>"]
    for s in v.get("shots", []):
        for p in s.get("problemi", []):
            lines.append(f"• {esc(s['id'])} {p.get('secondo', '')}s [{p.get('gravita')}] {esc(p.get('descrizione', ''))}")
    if v.get("loop"): lines.append(f"🔁 Loop: {esc(v['loop'])}")
    if v.get("trascurabili"): lines.append("Trascurabili: " + esc("; ".join(v["trascurabili"])))
    if v.get("rifacimento"): lines.append(f"↩️ Rifacimento da {v['rifacimento']['da_secondo']}s: {esc(v['rifacimento']['istruzioni_prompt'])}")
    for g in out.get("measures", {}).get("global", [])[:4]: lines.append("📏 " + esc(g))
    return "\n".join(lines)


def draft_buttons(ep, take):
    return [[{"text": "✅ Approva (1080p)", "callback_data": f"approve|{ep}|{take}"},
             {"text": "🔁 Rifai bozza", "callback_data": f"draft|{ep}|0"}]]


def final_buttons(ep, take):
    return [[{"text": "📅 Metti in coda su Buffer", "callback_data": f"schedule|{ep}|{take}"},
             {"text": "⏸ Non ora", "callback_data": f"noop|{ep}|{take}"}]]
