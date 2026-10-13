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
