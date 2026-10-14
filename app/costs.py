"""Registro costi: ogni generazione Kie, ogni giudizio OpenAI e le spese manuali finiscono in /data/<canale>/costs_log.csv.
Stesse colonne del registro locale (COSTI_PRODUZIONE.xlsx) più la voce 'servizio'."""
import csv, datetime
from . import config

COLS = ["data", "canale", "episodio", "take", "tipo", "servizio", "modello", "risoluzione", "durata_s", "crediti", "costo_usd",
        "esito", "task_id", "file", "credito_residuo", "note"]


def path():
    p = config.DATA / config.CHANNEL / "costs_log.csv"; p.parent.mkdir(parents=True, exist_ok=True); return p


def record(**row):
    p = path(); new = not p.exists()
    row.setdefault("data", datetime.datetime.now().isoformat(timespec="seconds")); row.setdefault("canale", config.CHANNEL)
    if row.get("costo_usd") in (None, "") and row.get("crediti") not in (None, ""):
        row["costo_usd"] = round(float(row["crediti"]) * config.KIE_CREDIT_USD, 2)
    with open(p, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, COLS, extrasaction="ignore")
        if new: w.writeheader()
        w.writerow(row)


def rows():
    p = path()
    return list(csv.DictReader(open(p, encoding="utf-8"))) if p.exists() else []


# ------------------------------------------------------------------ report (/costi)
GROUPS = [("bozze", "bozza"), ("1080p", "1080p Seedance"), ("upscale", "upscale"), ("AI", "AI testi e controlli"), ("altro", "altro")]


def _group(r):
    srv, tipo = (r.get("servizio") or "").lower(), (r.get("tipo") or "").lower()
    if srv == "kie": return "bozze" if "bozza" in tipo and "1080" not in tipo else "1080p"
    if srv == "fal": return "upscale"
    if srv == "openai": return "AI"
    return "altro"


def _when(r):
    import datetime as dt
    from zoneinfo import ZoneInfo
    try: d = dt.datetime.fromisoformat(r["data"])
    except Exception: return None
    if d.tzinfo is None: d = d.replace(tzinfo=dt.timezone.utc)          # il servizio registra l'ora del server (UTC)
    return d.astimezone(ZoneInfo("Europe/Rome"))


def _usd(r):
    try: return float(r.get("costo_usd") or 0)
    except ValueError: return 0.0


def report(ep: str | None = None) -> str:
    import datetime as dt
    from zoneinfo import ZoneInfo
    rs = rows()
    if not rs: return "Nessuna spesa registrata sul servizio (registro vuoto)."
    m = lambda v: f"{v:.2f}".replace(".", ",")
    if ep:
        mine = [r for r in rs if (r.get("episodio") or "").upper() == ep]
        if not mine: return f"Nessuna spesa registrata per {ep}."
        lines = [f"<b>Costi {ep}</b>", "<pre>"]
        for r in mine:
            w = _when(r); lines.append(f"{w:%d/%m %H:%M} " if w else "            ")
            lines[-1] += f"{(r.get('tipo') or '')[:24]:<24} {m(_usd(r)):>6}"
        tot = sum(_usd(r) for r in mine)
        lines += ["</pre>", f"Totale {ep}: <b>${m(tot)}</b>"]
        return "\n".join(lines)
    now = dt.datetime.now(ZoneInfo("Europe/Rome"))
    monday = (now - dt.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    prev = monday - dt.timedelta(days=7)

    def week(a, b):
        sel = [r for r in rs if (w := _when(r)) and a <= w < b]
        per = {}
        for r in sel:
            e = (r.get("episodio") or "").upper() or "varie"
            per.setdefault(e, {g: 0.0 for g, _ in GROUPS})[_group(r)] += _usd(r)
        return sel, per

    def block(title, a, b):
        sel, per = week(a, b); tot = sum(_usd(r) for r in sel)
        made = [e for e, v in per.items() if e != "varie" and (v["bozze"] or v["1080p"] or v["upscale"])]
        out = [f"<b>{title}</b> ({a:%d/%m}–{(b - dt.timedelta(days=1)):%d/%m}): <b>${m(tot)}</b>"
               + (f" · {len(made)} episod{'io' if len(made) == 1 else 'i'} · media ${m(sum(sum(per[e].values()) for e in made) / len(made))}/episodio" if made else "")]
        if per:
            out.append("<pre>ep     bozze 1080p   up   AI    tot")
            for e in sorted(per):
                v = per[e]; out.append(f"{e[:6]:<6}{m(v['bozze']):>6}{m(v['1080p']):>6}{m(v['upscale']):>5}{m(v['AI']):>5}{m(sum(v.values())):>7}")
            out.append("</pre>")
        return out

    lines = block("Questa settimana", monday, monday + dt.timedelta(days=7)) + block("Settimana scorsa", prev, monday)
    by = {g: 0.0 for g, _ in GROUPS}
    for r in rs: by[_group(r)] += _usd(r)
    first = min((w for r in rs if (w := _when(r))), default=None)
    lines.append("Sempre: " + " · ".join(f"{label} ${m(by[g])}" for g, label in GROUPS if by[g]))
    lines.append(f"Totale registrato: <b>${m(sum(by.values()))}</b>" + (f" (dal {first:%d/%m/%Y})" if first else ""))
    if any((r.get("servizio") == "openai" and not _usd(r)) for r in rs):
        lines.append("<i>I costi OpenAI risultano 0: imposta OPENAI_PRICE_IN_PER_M e OPENAI_PRICE_OUT_PER_M su Railway per contarli.</i>")
    lines.append("Dettaglio di un episodio: <code>/costi EP028</code>")
    return "\n".join(lines)
