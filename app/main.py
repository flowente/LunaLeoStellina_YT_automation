"""Servizio di produzione automatica degli short di "Luna, Leo e Stellina".

Flusso (n8n fa da regia e ti chiede l'ok):
  1. POST /episodes/{ep}/draft     -> bozza 480p + post-produzione + controllo (misure + giudice OpenAI) -> report a n8n
  2. POST /episodes/{ep}/approve   -> 1080p della take approvata (stesso video) + finale + copertina -> link a n8n (copia su Drive/PC)
  3. POST /episodes/{ep}/schedule  -> programmazione su Buffer (titolo, descrizione, per bambini, contenuto AI)
  4. POST /episodes/{ep}/cleanup   -> cancella i file temporanei da Supabase dopo la pubblicazione
Ogni chiamata richiede l'header  X-Token: <SERVICE_TOKEN>.
"""
import json, threading, traceback, uuid, datetime
from pathlib import Path
import requests
from fastapi import FastAPI, Header, HTTPException, Body
from fastapi.responses import FileResponse, PlainTextResponse
from . import config, episodes, kie, postprod, qc, judge, storage, buffer, costs

app = FastAPI(title="Luna Leo & Stellina — automazione short")
JOBS: dict = {}


# ------------------------------------------------------------------ utilità
def auth(token):
    if not config.SERVICE_TOKEN or token != config.SERVICE_TOKEN:
        raise HTTPException(401, "X-Token mancante o errato")


def ep_dir(ep):
    d = config.DATA / config.CHANNEL / "episodes" / ep; (d / "renders").mkdir(parents=True, exist_ok=True); return d


def state(ep):
    f = ep_dir(ep) / "state.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"episode": ep, "takes": {}}


def save_state(ep, s):
    (ep_dir(ep) / "state.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def notify(event, payload):
    if not config.N8N_WEBHOOK_URL: return
    try:
        requests.post(config.N8N_WEBHOOK_URL, json={"event": event, "channel": config.CHANNEL, **payload}, timeout=30)
    except Exception as e:
        print("webhook n8n non raggiunto:", e)


def run_job(kind, ep, fn, *args):
    jid = uuid.uuid4().hex[:12]
    JOBS[jid] = {"id": jid, "kind": kind, "episode": ep, "status": "running", "log": [], "started": datetime.datetime.now().isoformat(timespec="seconds")}
    def log(msg): JOBS[jid]["log"].append(msg); print(f"[{jid}] {msg}")
    def target():
        try:
            JOBS[jid]["result"] = fn(*args, log=log); JOBS[jid]["status"] = "done"
        except Exception as e:
            JOBS[jid].update(status="error", error=str(e)); log(traceback.format_exc())
            notify("error", {"episode": ep, "job": jid, "kind": kind, "error": str(e)})
    threading.Thread(target=target, daemon=True).start()
    return JOBS[jid]


def kie_generate(ep, take, req, stem: Path, tipo, log):
    before = kie.credit()
    task = kie.create(req); log(f"Kie task {task}")
    url, d = kie.wait(task, log=log)
    kie.download(url, stem.with_suffix(".mp4"))
    after = kie.credit()
    i = req["input"]
    costs.record(episodio=ep, take=take, tipo=tipo, servizio="kie", modello=req["model"], risoluzione=i.get("resolution"),
                 durata_s=i.get("duration", ""), crediti=d.get("creditsConsumed") or (before - after if before and after else ""),
                 esito="ok", task_id=task, file=stem.with_suffix(".mp4").name, credito_residuo=after)
    return task, stem.with_suffix(".mp4")


# ------------------------------------------------------------------ fasi
def do_draft(ep, log):
    E, req = episodes.request_for(ep, draft=True)
    s = state(ep); take = len(s["takes"]) + 1
    stem = ep_dir(ep) / "renders" / f"{ep}_take{take:02d}"
    stem.with_suffix(".request.json").write_text(json.dumps(req, ensure_ascii=False, indent=1), encoding="utf-8")
    task, raw = kie_generate(ep, take, req, stem, "bozza 480p", log)
    final = postprod.finalize(raw, E, episodes.channel()["post"]); log("post-produzione ok")
    rep = qc.analyze(raw, ep, ep_dir(ep) / "qc"); log(f"misure: {rep['esito']}")
    verdict = None
    try:
        verdict, usage, cost = judge.judge(final, ep, rep)
        costs.record(episodio=ep, take=take, tipo="controllo visivo", servizio="openai", modello=config.OPENAI_MODEL,
                     costo_usd=cost, esito="ok", note=json.dumps(usage))
        log(f"giudice: {verdict['verdetto']}")
    except Exception as e:
        log(f"giudice non eseguito: {e}")
    preview = storage.upload(final, f"{config.CHANNEL}/{ep}/{final.name}") if config.SUPABASE_KEY else None
    s["takes"][str(take)] = {"draft_task": task, "raw": raw.name, "final": final.name, "qc": rep, "verdict": verdict, "preview_url": preview}
    save_state(ep, s)
    out = {"episode": ep, "take": take, "preview_url": preview, "verdict": verdict, "measures": {"esito": rep["esito"], "global": rep["global_issues"]}}
    notify("draft_ready", out)
    return out


def do_approve(ep, take, log):
    E, _ = episodes.request_for(ep, draft=True); s = state(ep); t = s["takes"][str(take)]
    stem = ep_dir(ep) / "renders" / f"{ep}_take{take:02d}_1080p"
    task, raw = kie_generate(ep, take, kie.upgrade_request(t["draft_task"]), stem, "finale 1080p da bozza", log)
    final = postprod.finalize(raw, E, episodes.channel()["post"]); log("finale 1080p ok")
    cover = postprod.frame(final, float(E.get("cover_s", 1.0)), stem.with_name(f"{ep}_copertina_1080x1920.png"))
    up = lambda p: storage.upload(p, f"{config.CHANNEL}/{ep}/{p.name}")
    t.update(final_1080=final.name, final_url=up(final), cover_url=up(cover), approved=datetime.datetime.now().isoformat(timespec="seconds"))
    save_state(ep, s)
    out = {"episode": ep, "take": take, "final_url": t["final_url"], "cover_url": t["cover_url"], "file_name": final.name, **episodes.texts(ep)}
    notify("final_ready", out)
    return out


def do_schedule(ep, take, due_at, mode, log):
    s = state(ep); t = s["takes"][str(take)]
    if not t.get("final_url"): raise RuntimeError("Prima approva la take (finale 1080p non pronto)")
    post = buffer.schedule(ep, t["final_url"], due_at, mode)
    t["buffer_post"] = post; save_state(ep, s); log(f"Buffer: {post}")
    notify("scheduled", {"episode": ep, "take": take, "buffer": post})
    return post


# ------------------------------------------------------------------ API
@app.get("/health")
def health():
    return {"ok": True, "channel": config.CHANNEL,
            "keys": {k: bool(getattr(config, k)) for k in ("KIE_API_KEY", "OPENAI_API_KEY", "SUPABASE_KEY", "BUFFER_API_KEY", "N8N_WEBHOOK_URL")}}


@app.get("/episodes")
def list_episodes(x_token: str = Header(None)):
    auth(x_token); _, eps = episodes.all_episodes()
    return [{"id": k, "title": v["title"], "duration": v["duration"], "takes": len(state(k)["takes"])} for k, v in sorted(eps.items())]


@app.post("/episodes/{ep}/define")
def define(ep: str, spec: dict = Body(...), x_token: str = Header(None)):
    auth(x_token); episodes.define(ep, spec); episodes.request_for(ep)   # valida subito
    return {"ok": True, "episode": ep}


@app.get("/episodes/{ep}/request")
def show_request(ep: str, x_token: str = Header(None)):
    auth(x_token); E, req = episodes.request_for(ep); return {"request": req, "texts": episodes.texts(ep)}


@app.post("/episodes/{ep}/draft")
def draft(ep: str, x_token: str = Header(None)):
    auth(x_token); episodes.request_for(ep); return run_job("draft", ep, do_draft, ep)


@app.post("/episodes/{ep}/approve")
def approve(ep: str, take: int, x_token: str = Header(None)):
    auth(x_token); return run_job("approve", ep, do_approve, ep, take)


@app.post("/episodes/{ep}/schedule")
def schedule(ep: str, take: int, due_at: str | None = None, mode: str | None = None, x_token: str = Header(None)):
    auth(x_token); return run_job("schedule", ep, do_schedule, ep, take, due_at, mode)


@app.post("/episodes/{ep}/cleanup")
def cleanup(ep: str, x_token: str = Header(None)):
    auth(x_token); s = state(ep)
    paths = [f"{config.CHANNEL}/{ep}/{v[k].rsplit('/', 1)[-1]}" for v in s["takes"].values() for k in ("preview_url", "final_url", "cover_url") if v.get(k)]
    return storage.delete(paths) if paths else {"deleted": []}


@app.get("/episodes/{ep}")
def get_state(ep: str, x_token: str = Header(None)):
    auth(x_token); return state(ep)


@app.get("/episodes/{ep}/file/{name}")
def get_file(ep: str, name: str, x_token: str = Header(None)):
    auth(x_token); p = ep_dir(ep) / "renders" / Path(name).name
    if not p.exists(): raise HTTPException(404)
    return FileResponse(p)


@app.get("/jobs/{jid}")
def job(jid: str, x_token: str = Header(None)):
    auth(x_token)
    if jid not in JOBS: raise HTTPException(404, "job sconosciuto (il servizio potrebbe essere stato riavviato)")
    return JOBS[jid]


@app.get("/costs", response_class=PlainTextResponse)
def get_costs(x_token: str = Header(None)):
    auth(x_token); p = costs.path(); return p.read_text(encoding="utf-8") if p.exists() else ""


@app.post("/costs")
def add_cost(row: dict = Body(...), x_token: str = Header(None)):
    """Spese manuali (es. Railway, immagini): {"tipo":"Railway ottobre","servizio":"railway","costo_usd":5}"""
    auth(x_token); costs.record(**row); return {"ok": True}
