"""Servizio di produzione automatica degli short di "Luna, Leo e Stellina".

Flusso (n8n fa da regia e ti chiede l'ok):
  1. POST /episodes/{ep}/draft     -> bozza 480p + post-produzione + controllo (misure + giudice OpenAI) -> report a n8n
  2. POST /episodes/{ep}/approve   -> 1080p della take approvata (stesso video) + finale + copertina -> link a n8n (copia su Drive/PC)
  3. POST /episodes/{ep}/schedule  -> programmazione su Buffer (titolo, descrizione, per bambini, contenuto AI)
  4. POST /episodes/{ep}/cleanup   -> cancella i file temporanei da Supabase dopo la pubblicazione
Ogni chiamata richiede l'header  X-Token: <SERVICE_TOKEN>.
"""
import json, os, threading, traceback, uuid, datetime
from pathlib import Path
import requests
from fastapi import FastAPI, Header, HTTPException, Body, Request
from fastapi.responses import FileResponse, PlainTextResponse
from . import config, episodes, kie, postprod, qc, judge, storage, buffer, costs, telegram, writer, upscale

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
    try:
        if telegram.enabled():
            ep, take = payload.get("episode"), payload.get("take")
            if event == "draft_ready":
                txt = telegram.draft_report(payload)
                if payload.get("preview_url"): telegram.send_video(payload["preview_url"], txt, telegram.draft_buttons(ep, take))
                else: telegram.send(txt, telegram.draft_buttons(ep, take))
            elif event == "final_ready":
                via = " · upscale fal" if payload.get("provider") == "fal" else ""
                telegram.send(f"<b>{ep}</b> · finale 1080p pronto{via} (copia su Drive in corso).\n"
                              f'<a href="{payload["final_url"]}">Finale</a> · <a href="{payload["cover_url"]}">Copertina</a>\n\n'
                              f"<b>Titolo:</b> {telegram.esc(payload['title_it'])}\n<b>EN:</b> {telegram.esc(payload['title_en'])}",
                              telegram.final_buttons(ep, take))
            elif event == "scheduled":
                telegram.send(f"<b>{ep}</b> · programmato su Buffer: {telegram.esc(payload['buffer'].get('dueAt') or 'in coda')}")
            elif event == "error":
                telegram.send(f"⚠️ <b>{ep}</b> · errore in {payload.get('kind')}: {telegram.esc(payload.get('error'))}")
            elif event == "started" and payload.get("kind") not in ("proposta", "idee", "brainstorming"):
                telegram.send(f"<b>{ep}</b> · {'bozza' if payload.get('kind')=='draft' else payload.get('kind')} avviata")
    except Exception as e:
        print("telegram:", e)
    if not config.N8N_WEBHOOK_URL: return
    try:
        requests.post(config.N8N_WEBHOOK_URL, json={"event": event, "channel": config.CHANNEL, **payload}, timeout=30)
    except Exception as e:
        print("webhook n8n non raggiunto:", e)


def progress(ep, text):
    """Aggiornamento breve su Telegram durante un lavoro."""
    try:
        if telegram.enabled(): telegram.send(f"<b>{ep}</b> · {telegram.esc(text)}")
    except Exception as e:
        print("telegram:", e)


def run_job(kind, ep, fn, *args, **kw):
    jid = uuid.uuid4().hex[:12]
    JOBS[jid] = {"id": jid, "kind": kind, "episode": ep, "status": "running", "log": [], "started": datetime.datetime.now().isoformat(timespec="seconds")}
    def log(msg): JOBS[jid]["log"].append(msg); print(f"[{jid}] {msg}")
    def target():
        try:
            JOBS[jid]["result"] = fn(*args, log=log, **kw); JOBS[jid]["status"] = "done"
        except Exception as e:
            JOBS[jid].update(status="error", error=str(e)); log(traceback.format_exc())
            notify("error", {"episode": ep, "job": jid, "kind": kind, "error": str(e)})
    threading.Thread(target=target, daemon=True).start()
    notify("started", {"episode": ep, "kind": kind})
    return JOBS[jid]


def kie_generate(ep, take, req, stem: Path, tipo, log, kind="draft", task=None):
    before = kie.credit()
    if not task:
        task = kie.create(req); log(f"Kie task {task}")
        progress(ep, f"{tipo}: generazione avviata su Seedance (di solito 2-4 minuti)")
        st = state(ep); st.setdefault("pending", {})[kind] = {"task": task, "take": take}; save_state(ep, st)   # ripresa dopo un riavvio
    else:
        log(f"Ripresa del task Kie {task} dopo un riavvio")
        progress(ep, f"{tipo}: riprendo la generazione interrotta dal riavvio del servizio")
    url, d = kie.wait(task, log=log)
    kie.download(url, stem.with_suffix(".mp4"))
    after = kie.credit()
    i = req["input"]
    costs.record(episodio=ep, take=take, tipo=tipo, servizio="kie", modello=req["model"], risoluzione=i.get("resolution"),
                 durata_s=i.get("duration", ""), crediti=d.get("creditsConsumed") or (before - after if before and after else ""),
                 esito="ok", task_id=task, file=stem.with_suffix(".mp4").name, credito_residuo=after)
    st = state(ep); st.get("pending", {}).pop(kind, None); save_state(ep, st)
    return task, stem.with_suffix(".mp4")


# ------------------------------------------------------------------ fasi
def do_draft(ep, log, resume=None):
    E, req = episodes.request_for(ep, draft=True)
    if not resume:
        st0 = state(ep); st0.pop("aborted", None); save_state(ep, st0)
    s = state(ep); take = resume["take"] if resume else len(s["takes"]) + 1
    stem = ep_dir(ep) / "renders" / f"{ep}_take{take:02d}"
    stem.with_suffix(".request.json").write_text(json.dumps(req, ensure_ascii=False, indent=1), encoding="utf-8")
    task, raw = kie_generate(ep, take, req, stem, "bozza 480p", log, "draft", (resume or {}).get("task"))
    s = state(ep)
    if s.get("aborted"):
        progress(ep, "produzione annullata: bozza scaricata ma non elaborata"); return {"episode": ep, "aborted": True}
    progress(ep, "video ricevuto: post-produzione (colori, loop, audio)")
    final = postprod.finalize(raw, E, episodes.channel()["post"]); log("post-produzione ok")
    progress(ep, "controllo qualità in corso (misure e giudice)")
    rep = qc.analyze(raw, ep, ep_dir(ep) / "qc"); log(f"misure: {rep['esito']}")
    verdict = None
    try:
        verdict, usage, cost = judge.judge(final, ep, rep)
        costs.record(episodio=ep, take=take, tipo="controllo visivo", servizio="openai", modello=config.OPENAI_MODEL,
                     costo_usd=cost, esito="ok", note=json.dumps(usage))
        log(f"giudice: {verdict['verdetto']}")
    except Exception as e:
        log(f"giudice non eseguito: {e}")
    preview = storage.upload(final, f"{config.SUPABASE_VIDEO_PREFIX}/{config.CHANNEL}/{ep}/{final.name}") if config.SUPABASE_KEY else None
    s["takes"][str(take)] = {"draft_task": task, "raw": raw.name, "final": final.name, "qc": rep, "verdict": verdict, "preview_url": preview}
    save_state(ep, s)
    out = {"episode": ep, "take": take, "preview_url": preview, "verdict": verdict, "measures": {"esito": rep["esito"], "global": rep["global_issues"]}}
    notify("draft_ready", out)
    return out


def do_approve(ep, take, log, resume=None):
    if config.UPSCALE_PROVIDER == "fal":            # interruttore: strada nuova (bozza + upscale fal)
        return do_upscale(ep, take, log, as_final=True)
    E, _ = episodes.request_for(ep, draft=True); s = state(ep); t = s["takes"][str(take)]
    stem = ep_dir(ep) / "renders" / f"{ep}_take{take:02d}_1080p"
    task, raw = kie_generate(ep, take, kie.upgrade_request(t["draft_task"]), stem, "finale 1080p da bozza", log, "approve", (resume or {}).get("task"))
    s = state(ep); t = s["takes"][str(take)]
    progress(ep, "1080p ricevuto: post-produzione e copertina")
    final = postprod.finalize(raw, E, episodes.channel()["post"]); log("finale 1080p ok")
    cover = postprod.frame(final, float(E.get("cover_s", 1.0)), stem.with_name(f"{ep}_copertina_1080x1920.png"))
    up = lambda p: storage.upload(p, f"{config.SUPABASE_VIDEO_PREFIX}/{config.CHANNEL}/{ep}/{p.name}")
    t.update(final_1080=final.name, final_url=up(final), cover_url=up(cover), approved=datetime.datetime.now().isoformat(timespec="seconds"))
    save_state(ep, s)
    out = {"episode": ep, "take": take, "final_url": t["final_url"], "cover_url": t["cover_url"], "file_name": final.name,
           "provider": "seedance", **episodes.texts(ep)}
    notify("final_ready", out)
    return out


def check_vs_draft(draft_final: Path, up_final: Path) -> dict:
    """Confronto strutturale upscale vs bozza (stessa scena): trova dove l'upscaler ha cambiato forme o volti."""
    import cv2, numpy as np
    def frames(p):
        c = cv2.VideoCapture(str(p)); fs = []
        while True:
            ok, f = c.read()
            if not ok: break
            fs.append(cv2.cvtColor(cv2.resize(f, (270, 480), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32))
        return fs, c.get(cv2.CAP_PROP_FPS) or 24
    def ssim(a, b):
        g = lambda x: cv2.GaussianBlur(x, (7, 7), 1.5); C1, C2 = 6.5025, 58.5225
        ma, mb = g(a), g(b); va, vb, cab = g(a * a) - ma * ma, g(b * b) - mb * mb, g(a * b) - ma * mb
        return float((((2 * ma * mb + C1) * (2 * cab + C2)) / ((ma * ma + mb * mb + C1) * (va + vb + C2))).mean())
    A, fps = frames(draft_final); B, _ = frames(up_final); n = min(len(A), len(B))
    if not n: return {"esito": "non misurabile"}
    sc = [ssim(A[i], B[i]) for i in range(0, n, 2)]
    worst = int(np.argmin(sc)); low = [round(i * 2 / fps, 1) for i, v in enumerate(sc) if v < 0.80]
    return {"ssim_medio": round(float(np.mean(sc)), 3), "ssim_min": round(float(sc[worst]), 3), "secondo_peggiore": round(worst * 2 / fps, 1),
            "secondi_da_guardare": low[:10], "esito": "ok" if not low else "da guardare"}


def do_upscale(ep, take, log, as_final=False, resume=None):
    """Bozza 480p -> 1080p con SeedVR2 su fal. as_final=True quando lo usa "Approva" (UPSCALE_PROVIDER=fal),
    altrimenti è una prova (/upscale): il finale Seedance, se esiste, non viene toccato."""
    E, _ = episodes.request_for(ep, draft=True); s = state(ep); t = s["takes"][str(take)]
    rd = ep_dir(ep) / "renders"
    raw = rd / t["raw"] if t.get("raw") else None
    # due sorgenti: la bozza GREZZA sul volume (normale) oppure, per episodi già fatti, la bozza già post-prodotta
    # recuperata da Supabase: in quel caso colori, loop e audio sono già applicati e non si rifà finalize
    from_raw = bool(raw and raw.exists())
    if not from_raw:
        if not t.get("preview_url"): raise RuntimeError(f"bozza non trovata né sul volume né su Supabase per {ep} take {take}")
        raw = rd / t["final"]
        if not raw.exists(): upscale.download(t["preview_url"], raw)
    if resume:
        job = {k: resume[k] for k in ("request_id", "status_url", "response_url")}
        progress(ep, "upscale: riprendo la richiesta fal interrotta dal riavvio")
    else:
        if from_raw:
            src_url = storage.upload(raw, f"{config.SUPABASE_VIDEO_PREFIX}/{config.CHANNEL}/{ep}/{raw.name}")
            t["raw_url"] = src_url; save_state(ep, s)
        else:
            src_url = t["preview_url"]
        job = upscale.submit(src_url); log(f"fal {job['request_id']}")
        st = state(ep); st.setdefault("pending", {})["upscale"] = {**job, "take": take, "as_final": as_final}; save_state(ep, st)
        progress(ep, f"take {take}: upscale a 1080p avviato su fal (di solito 2-5 minuti)")
    res = upscale.wait(job, log=log)
    stem = ep_dir(ep) / "renders" / f"{ep}_take{take:02d}_1080p_up"
    fal_out = upscale.download(res["video"]["url"], stem.with_name(stem.name + "_fal.mp4"))
    cost, p = upscale.cost_usd(fal_out)
    costs.record(episodio=ep, take=take, tipo="upscale 1080p da bozza", servizio="fal", modello=config.FAL_UPSCALE_MODEL,
                 risoluzione=f"{p['w']}x{p['h']}", durata_s=round(p["frames"] / 24, 2), costo_usd=cost, esito="ok",
                 task_id=job["request_id"], file=fal_out.name,
                 note=f"noise {config.FAL_UPSCALE_NOISE}, seed {config.FAL_UPSCALE_SEED}, fix {config.UPSCALE_FIX_VF}")
    st = state(ep); st.get("pending", {}).pop("upscale", None); save_state(ep, st)
    progress(ep, "upscale ricevuto: correzione colore, post-produzione e confronto con la bozza")
    if from_raw:
        conformed = upscale.conform(fal_out, raw, stem.with_suffix(".mp4"))
        final = postprod.finalize(conformed, E, episodes.channel()["post"])
    else:
        final = upscale.conform(fal_out, raw, stem.with_name(stem.name + "_final.mp4"))
    log("finale upscale ok")
    check = check_vs_draft(ep_dir(ep) / "renders" / t["final"], final) if t.get("final") else {"esito": "non misurabile"}
    cover = postprod.frame(final, float(E.get("cover_s", 1.0)), stem.with_name(f"{ep}_copertina_up_1080x1920.png"))
    up = lambda q: storage.upload(q, f"{config.SUPABASE_VIDEO_PREFIX}/{config.CHANNEL}/{ep}/{q.name}")
    s = state(ep); t = s["takes"][str(take)]
    t["upscale"] = {"file": final.name, "url": up(final), "cover_url": up(cover), "costo_usd": cost, "confronto": check,
                    "request_id": job["request_id"], "creato": datetime.datetime.now().isoformat(timespec="seconds")}
    if as_final: use_upscale_as_final(t)
    save_state(ep, s)
    out = {"episode": ep, "take": take, "final_url": t["upscale"]["url"], "cover_url": t["upscale"]["cover_url"], "file_name": final.name,
           "provider": "fal", "costo_usd": cost, "confronto": check, **episodes.texts(ep)}
    if as_final:
        notify("final_ready", out)
    else:
        seed_note = "C'è già un finale Seedance: se usi questo, lo sostituisce." if t.get("final_url") else "Questa take non ha ancora un finale."
        telegram.send(f"<b>{ep}</b> · PROVA upscale fal take {take} pronta · ${cost:.2f}\n"
                      f'<a href="{out["final_url"]}">Video</a> · <a href="{out["cover_url"]}">Copertina</a>\n'
                      f"Confronto con la bozza: {telegram.esc(check.get('esito'))} (somiglianza media {check.get('ssim_medio', '-')}, "
                      f"minima {check.get('ssim_min', '-')} a {check.get('secondo_peggiore', '-')}s)\n{seed_note}",
                      [[{"text": "Usa come finale", "callback_data": f"useup|{ep}|{take}"},
                        {"text": "Non ora", "callback_data": f"noop|{ep}|{take}"}]])
    return out


def recover_take(ep, take):
    """Episodi prodotti prima di un riavvio senza volume, o fuori dal servizio: recupera la bozza da Supabase."""
    name = f"{ep}_take{take:02d}_final.mp4"
    url = storage.public_url(f"{config.SUPABASE_VIDEO_PREFIX}/{config.CHANNEL}/{ep}/{name}")
    if requests.head(url, timeout=30).status_code != 200: return None
    s = state(ep); s["takes"][str(take)] = {"final": name, "preview_url": url, "recuperata": "supabase"}
    fin = url.replace(name, f"{ep}_take{take:02d}_1080p_final.mp4")
    if requests.head(fin, timeout=30).status_code == 200:
        s["takes"][str(take)].update(final_url=fin, final_1080=fin.rsplit("/", 1)[-1])
    save_state(ep, s); return s["takes"][str(take)]


def start_upscale(ep, want=None):
    if not config.FAL_KEY: raise RuntimeError("FAL_KEY non impostata nelle variabili di Railway")
    episodes.request_for(ep); st = state(ep)
    if not st["takes"] or (want and str(want) not in st["takes"]):
        if not recover_take(ep, want or 1):
            raise RuntimeError(f"{ep}: nessuna bozza{f' take {want}' if want else ''} né sul servizio né su Supabase")
        telegram.send(f"<b>{ep}</b> · bozza recuperata da Supabase (già post-prodotta: faccio solo l'upscale e la correzione)")
        st = state(ep)
    take = want or int(sorted(st["takes"], key=int)[-1])
    run_job("upscale", ep, do_upscale, ep, take, as_final=False)


def episode_buttons(action, n=8):
    """Pulsanti con gli ultimi episodi: dal menu "/" Telegram manda il comando senza episodio."""
    _, eps = episodes.all_episodes(); ids = sorted(eps)[-n:][::-1]
    return [[{"text": e, "callback_data": f"{action}|{e}|0"} for e in ids[i:i + 4]] for i in range(0, len(ids), 4)]


def use_upscale_as_final(t):
    u = t["upscale"]
    if t.get("final_url") and not t.get("final_seedance"):        # tiene traccia del finale Seedance sostituito
        t["final_seedance"] = {"file": t.get("final_1080"), "url": t["final_url"], "cover_url": t.get("cover_url")}
    t.update(final_1080=u["file"], final_url=u["url"], cover_url=u["cover_url"], final_provider="fal",
             approved=datetime.datetime.now().isoformat(timespec="seconds"))


def do_schedule(ep, take, due_at, mode, log):
    s = state(ep); t = s["takes"][str(take)]
    if not t.get("final_url"): raise RuntimeError("Prima approva la take (finale 1080p non pronto)")
    post = buffer.schedule(ep, t["final_url"], due_at, mode)
    t["buffer_post"] = post; save_state(ep, s); log(f"Buffer: {post}")
    notify("scheduled", {"episode": ep, "take": take, "buffer": post})
    return post


# ------------------------------------------------------------------ API
@app.get("/health")
def volume_ok():
    """Il volume Railway è montato su DATA_DIR? Senza volume stato episodi e registro costi spariscono a ogni deploy."""
    return os.path.ismount(config.DATA)


def health():
    return {"ok": True, "channel": config.CHANNEL, "volume_data_montato": volume_ok(),
            "upscale_provider": config.UPSCALE_PROVIDER,
            "keys": {**{k: bool(getattr(config, k)) for k in ("KIE_API_KEY", "OPENAI_API_KEY", "SUPABASE_KEY", "BUFFER_API_KEY", "N8N_WEBHOOK_URL", "FAL_KEY")},
                     "TELEGRAM_BOT_TOKEN": bool(telegram.TOKEN), "TELEGRAM_CHAT_ID": bool(telegram.CHAT)}}


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
    urls = [v[k] for v in s["takes"].values() for k in ("preview_url", "final_url", "cover_url", "raw_url") if v.get(k)]
    urls += [v["upscale"][k] for v in s["takes"].values() if v.get("upscale") for k in ("url", "cover_url") if v["upscale"].get(k)]
    urls += [v["final_seedance"][k] for v in s["takes"].values() if v.get("final_seedance") for k in ("url", "cover_url") if v["final_seedance"].get(k)]
    paths = sorted({f"{config.SUPABASE_VIDEO_PREFIX}/{config.CHANNEL}/{ep}/{u.rsplit('/', 1)[-1]}" for u in urls})
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


def abort(ep):
    st = state(ep); st["aborted"] = datetime.datetime.now().isoformat(timespec="seconds"); st.pop("pending", None); save_state(ep, st)
    telegram.send(f"<b>{ep}</b> · produzione annullata. Nessuna bozza nuova e nessun 1080p. "
                  f"(Se una generazione era già partita su Seedance, il costo è già stato speso.)")


# ------------------------------------------------------------------ brainstorming
def brain_file():
    d = config.DATA / config.CHANNEL; d.mkdir(parents=True, exist_ok=True); return d / "brainstorming.json"


def brain_load():
    f = brain_file(); return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def brain_save(b):
    brain_file().write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")


def brain_close():
    brain_file().unlink(missing_ok=True)


def do_brainstorm(ep, text, log):
    b = brain_load() or {"history": [], "started": datetime.datetime.now().isoformat(timespec="seconds")}
    b["history"].append({"chi": "simone", "testo": text})
    out, usage, cost = writer.brainstorm(b["history"])
    costs.record(tipo="brainstorming", servizio="openai", modello=config.OPENAI_IDEAS_MODEL, costo_usd=cost, esito="ok", note=json.dumps(usage))
    b["history"].append({"chi": "autore", "testo": f"{out['risposta']}\n[pacchetto] {out['titolo']}: {out['descrizione']}"})
    b["pack"] = {"titolo": out["titolo"], "descrizione": out["descrizione"]}; brain_save(b)
    telegram.send(f"{telegram.esc(out['risposta'])}\n\n📦 <b>{telegram.esc(out['titolo'])}</b>\n{telegram.esc(out['descrizione'])}\n\n"
                  "<i>Scrivimi pure per correggere o aggiungere. Quando ti convince, conferma.</i>",
                  [[{"text": "Confermo: scrivi l'episodio", "callback_data": "brain_ok|IDEA|0"},
                    {"text": "Chiudi", "callback_data": "brain_no|IDEA|0"}]])
    return b["pack"]


def ideas_file():
    d = config.DATA / config.CHANNEL; d.mkdir(parents=True, exist_ok=True); return d / "idee.json"


def do_ideas(ep, tema, log):
    ideas, usage, cost = writer.concepts(tema)
    costs.record(tipo="idee", servizio="openai", modello=config.OPENAI_IDEAS_MODEL, costo_usd=cost, esito="ok", note=json.dumps(usage))
    ideas_file().write_text(json.dumps({"tema": tema, "idee": ideas}, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"<b>Idee{(' · ' + telegram.esc(tema)) if tema else ''}</b>"]
    for i, it in enumerate(ideas, 1):
        lines.append(f"\n<b>{i}. {telegram.esc(it['titolo'])}</b>\n{telegram.esc(it['descrizione'])}")
    lines.append("\n✅ = scrivi l'episodio · 💬 = ragioniamoci sopra")
    rows = [[{"text": f"✅ {i}", "callback_data": f"idea_ok|IDEA|{i}"}, {"text": f"💬 {i}", "callback_data": f"idea_talk|IDEA|{i}"}]
            for i in range(1, len(ideas) + 1)]
    rows.append([{"text": "Altre idee", "callback_data": "idea_more|IDEA|0"}])
    telegram.send("\n".join(lines), rows)
    return ideas


def propose_from(titolo, descrizione):
    ep_new = writer.next_id()
    telegram.send(f"<b>{ep_new}</b> · scrivo la proposta da «{telegram.esc(titolo)}»…")
    run_job("proposta", ep_new, do_propose, ep_new, f"{titolo}. {descrizione}")


def prop_file(ep):
    d = config.DATA / config.CHANNEL / "proposals"; d.mkdir(parents=True, exist_ok=True); return d / f"{ep}.json"


def do_propose(ep, idea, log, feedback=""):
    spec, usage, cost = writer.write(idea, feedback)
    costs.record(episodio=ep, tipo="scrittura episodio", servizio="openai", modello=config.OPENAI_MODEL, costo_usd=cost, esito="ok", note=json.dumps(usage))
    prop_file(ep).write_text(json.dumps({"idea": idea, "spec": spec}, ensure_ascii=False, indent=1), encoding="utf-8")
    sp = dict(spec); summary = sp.pop("riassunto_it", "")
    episodes.define(ep + "_check", sp); episodes.request_for(ep + "_check")      # verifica formato
    f = episodes.extra_file(); d = json.loads(f.read_text(encoding="utf-8")); d.pop(ep + "_check", None); f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    telegram.send(f"<b>{ep}</b> · proposta: <b>{telegram.esc(spec['title'])}</b> ({spec['duration']}s, {spec['world']})\n"
                  f"{telegram.esc(summary)}\n\nTitolo: {telegram.esc(spec['title_it'])}",
                  [[{"text": "Ok, fai la bozza", "callback_data": f"nuovo_ok|{ep}|0"},
                    {"text": "Rifai idea", "callback_data": f"nuovo_rifai|{ep}|0"},
                    {"text": "Annulla", "callback_data": f"nuovo_no|{ep}|0"}]])
    return {"episode": ep, "title": spec["title"]}


def do_revise(ep, change, log):
    _, eps = episodes.all_episodes()
    spec, usage, cost = writer.revise(eps[ep], change)
    costs.record(episodio=ep, tipo="modifica episodio", servizio="openai", modello=config.OPENAI_MODEL, costo_usd=cost, esito="ok", note=json.dumps(usage))
    keep = {k: v for k, v in eps[ep].items() if k not in spec}          # campi non gestiti dallo scrittore (overlay, glow, props...)
    new = {**keep, **spec}; summary = new.pop("riassunto_it", "")
    episodes.define(ep + "_check", new); episodes.request_for(ep + "_check")
    f = episodes.extra_file(); d = json.loads(f.read_text(encoding="utf-8")); d.pop(ep + "_check", None); f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    prop_file(ep).write_text(json.dumps({"idea": change, "spec": new, "revision": True}, ensure_ascii=False, indent=1), encoding="utf-8")
    telegram.send(f"<b>{ep}</b> · modifica proposta:\n{telegram.esc(summary)}",
                  [[{"text": "Ok, rifai la bozza", "callback_data": f"nuovo_ok|{ep}|0"},
                    {"text": "Salva senza bozza", "callback_data": f"mod_save|{ep}|0"}],
                   [{"text": "Annulla modifica", "callback_data": f"nuovo_no|{ep}|0"}]])
    return {"episode": ep}


# ------------------------------------------------------------------ Telegram
@app.on_event("startup")
def _tg_startup():
    def reg():
        try: print("telegram webhook:", telegram.set_webhook(), flush=True)
        except Exception as e: print("telegram webhook non impostato:", e, flush=True)
    threading.Thread(target=reg, daemon=True).start()   # mai bloccare l'avvio del servizio
    # stato al riavvio: lavori ripresi e bozze interrotte prima che il servizio sapesse riprenderle
    resumed, lost = [], []
    for d in (config.DATA / config.CHANNEL / "episodes").glob("*"):
        st = state(d.name)
        if st.get("pending"): resumed.append(d.name)
        for rq in (d / "renders").glob("*_take??.request.json"):
            take = rq.name.split("_take")[1][:2]
            flag = rq.with_name(rq.name.replace(".request.json", ".interrotta"))
            if str(int(take)) not in st["takes"] and not st.get("pending") and not flag.exists():
                lost.append(f"{d.name} take {int(take)}"); flag.write_text("segnalata")
    lines = [f"Servizio avviato. Finale con: {'upscale fal' if config.UPSCALE_PROVIDER == 'fal' else 'Seedance 1080p'}."]
    lines.append(f"Volume {config.DATA}: montato ✔" if volume_ok() else
                 f"⚠️ Volume {config.DATA} NON montato: stato degli episodi e registro costi si perdono a ogni deploy. "
                 "Railway → servizio → tasto destro / ⋮ → Attach Volume → mount path /data")
    lines.append("Riprendo: " + ", ".join(resumed) if resumed else "Nessun lavoro in corso.")
    if lost: lines.append("Interrotte dal riavvio, da rilanciare: " + ", ".join(lost) + " (usa /bozza).")
    lines.append("Comandi: /episodi · /nuovo idea · /idee · /brainstorming · /modifica EP0xx correzione · /bozza EP0xx · /upscale EP0xx · /annulla EP0xx · /stato EP0xx · /programma EP0xx 20/10 17:30 · /costi")
    try:
        if telegram.enabled(): threading.Thread(target=telegram.send, args=("\n".join(lines),), daemon=True).start()
    except Exception as e:
        print("telegram:", e)
    # riprende le generazioni interrotte da un riavvio (il task su Kie continua anche se il servizio si ferma)
    for f in (config.DATA / config.CHANNEL / "episodes").glob("*/state.json"):
        try:
            st = json.loads(f.read_text(encoding="utf-8")); ep = st.get("episode") or f.parent.name
            if st.get("aborted"): continue
            for kind, p in (st.get("pending") or {}).items():
                if kind == "draft": run_job("draft", ep, do_draft, ep, resume=p)
                elif kind == "approve": run_job("approve", ep, do_approve, ep, p["take"], resume=p)
                elif kind == "upscale": run_job("upscale", ep, do_upscale, ep, p["take"], as_final=p.get("as_final", False), resume=p)
        except Exception as e:
            print("ripresa non riuscita:", f, e)


@app.get("/telegram/status")
def telegram_status(x_token: str = Header(None)):
    auth(x_token)
    info = telegram.call("getWebhookInfo") or {}
    r = info.get("result", {})
    return {"token_ok": bool(info.get("ok")), "webhook_url": r.get("url"), "last_error": r.get("last_error_message"),
            "pending": r.get("pending_update_count"), "domain": os.environ.get("RAILWAY_PUBLIC_DOMAIN")}


@app.post("/telegram/register")
def telegram_register(x_token: str = Header(None)):
    auth(x_token); return telegram.set_webhook() or {"ok": False, "motivo": "token o dominio mancante"}


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str = Header(None)):
    if not telegram.check_secret(x_telegram_bot_api_secret_token): raise HTTPException(401)
    u = await request.json()
    if "callback_query" in u:
        q = u["callback_query"]; chat = str(q["message"]["chat"]["id"])
        telegram.call("answerCallbackQuery", callback_query_id=q["id"])
        if chat != str(telegram.CHAT): return {"ok": True}
        action, ep, take = (q.get("data", "") + "||").split("|")[:3]
        take = int(take or 0)
        if action == "approve": run_job("approve", ep, do_approve, ep, take)
        elif action == "draft": run_job("draft", ep, do_draft, ep)
        elif action == "schedule": run_job("schedule", ep, do_schedule, ep, take, None, None)
        elif action == "noop": telegram.send(f"Ok, {ep} resta pronto senza programmazione.")
        elif action == "brain_ok":
            b = brain_load()
            if not b or not b.get("pack"): telegram.send("Nessun brainstorming aperto.")
            else: brain_close(); propose_from(b["pack"]["titolo"], b["pack"]["descrizione"])
        elif action == "brain_no":
            brain_close(); telegram.send("Brainstorming chiuso.")
        elif action in ("idea_ok", "idea_talk", "idea_more"):
            data = json.loads(ideas_file().read_text(encoding="utf-8")) if ideas_file().exists() else {"idee": [], "tema": ""}
            if action == "idea_more": run_job("idee", "IDEE", do_ideas, "IDEE", data.get("tema", ""))
            elif not 0 < take <= len(data["idee"]): telegram.send("Idea non trovata: rilancia /idee")
            else:
                it = data["idee"][take - 1]
                if action == "idea_ok": propose_from(it["titolo"], it["descrizione"])
                else:
                    brain_close(); telegram.send(f"Ragioniamo su «{telegram.esc(it['titolo'])}»…")
                    run_job("brainstorming", "IDEA", do_brainstorm, "IDEA",
                            f"Partiamo da questa idea: {it['titolo']}. {it['descrizione']} Dimmi come la renderesti più forte.")
        elif action == "cmd_upscale":
            try: start_upscale(ep)
            except Exception as e: telegram.send(f"⚠️ {telegram.esc(e)}")
        elif action == "cmd_stato":
            st = state(ep)
            telegram.send(f"<b>{ep}</b>: {len(st['takes'])} take" + "".join(
                f"\ntake {k}: {(v.get('verdict') or {}).get('verdetto', '-')}{' · finale pronto' if v.get('final_url') else ''}"
                for k, v in st["takes"].items()))
        elif action == "useup":
            s = state(ep); t = s["takes"][str(take)]
            if not t.get("upscale"): telegram.send(f"<b>{ep}</b> · nessun upscale per la take {take}")
            else:
                use_upscale_as_final(t); save_state(ep, s)
                notify("final_ready", {"episode": ep, "take": take, "final_url": t["final_url"], "cover_url": t["cover_url"],
                                       "file_name": t["final_1080"], "provider": "fal", **episodes.texts(ep)})   # Telegram + copia su Drive (n8n)
        elif action == "abort": abort(ep)
        elif action == "nuovo_ok":
            pr = json.loads(prop_file(ep).read_text(encoding="utf-8")); sp = dict(pr["spec"]); sp.pop("riassunto_it", None)
            episodes.define(ep, sp); prop_file(ep).unlink(missing_ok=True)
            run_job("draft", ep, do_draft, ep)
        elif action == "mod_save":
            pr = json.loads(prop_file(ep).read_text(encoding="utf-8")); sp = dict(pr["spec"]); sp.pop("riassunto_it", None)
            episodes.define(ep, sp); prop_file(ep).unlink(missing_ok=True)
            telegram.send(f"<b>{ep}</b> · modifica salvata. Lancia la bozza quando vuoi con /bozza {ep}")
        elif action == "nuovo_rifai":
            pr = json.loads(prop_file(ep).read_text(encoding="utf-8"))
            run_job("proposta", ep, do_propose, ep, pr["idea"], feedback="proponi una versione diversa")
        elif action == "nuovo_no":
            prop_file(ep).unlink(missing_ok=True); telegram.send(f"Proposta {ep} annullata.")
        return {"ok": True}
    m = u.get("message") or {}; chat = str((m.get("chat") or {}).get("id", "")); text = (m.get("text") or "").strip()
    if not text: return {"ok": True}
    if text.split()[0].lower().split("@")[0] in ("/id", "/start"):      # esatto: "/idee" non deve finire qui
        telegram.send(f"Il tuo chat id è <code>{chat}</code>", chat=chat); return {"ok": True}
    if chat != str(telegram.CHAT): return {"ok": True}
    if not text.startswith("/"):
        if brain_load() is not None: run_job("brainstorming", "IDEA", do_brainstorm, "IDEA", text)
        else: telegram.send("Per ragionare su un'idea scrivi <code>/brainstorming</code> seguito dall'idea, anche abbozzata. "
                            "Per idee già pronte: <code>/idee</code> (oppure <code>/idee colori</code>).")
        return {"ok": True}
    parts = text.split(); cmd = parts[0].lower().split("@")[0]; arg = parts[1].upper() if len(parts) > 1 else ""
    needs_ep = {"/bozza": "/bozza EP027", "/upscale": "/upscale EP028  (oppure /upscale EP028 2 per la take 2)",
                "/stato": "/stato EP027", "/annulla": "/annulla EP027", "/modifica": "/modifica EP027 correzione",
                "/programma": "/programma EP027 20/10 17:30  oppure  /programma EP027 coda"}
    if cmd in needs_ep and not arg:
        pick = {"/upscale": "cmd_upscale", "/stato": "cmd_stato"}.get(cmd)
        telegram.send(f"{'Scegli l’episodio, oppure scrivi' if pick else 'Manca l’episodio. Scrivi così'}: "
                      f"<code>{telegram.esc(needs_ep[cmd])}</code>", episode_buttons(pick) if pick else None)
        return {"ok": True}
    try:
        if cmd == "/bozza" and arg:
            episodes.request_for(arg); run_job("draft", arg, do_draft, arg)
        elif cmd == "/upscale" and arg:
            # /upscale EP028   (ultima take)   oppure   /upscale EP028 2
            start_upscale(arg, int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None)
        elif cmd == "/stato" and arg:
            st = state(arg)
            telegram.send(f"<b>{arg}</b>: {len(st['takes'])} take\n" + "\n".join(
                f"take {k}: {(v.get('verdict') or {}).get('verdetto', '-')}{' · finale pronto' if v.get('final_url') else ''}"
                f"{' (upscale fal)' if v.get('final_provider') == 'fal' else ''}"
                f"{' · prova upscale' if v.get('upscale') and v.get('final_provider') != 'fal' else ''}"
                f"{' · programmato' if v.get('buffer_post') else ''}" for k, v in st["takes"].items()))
        elif cmd == "/annulla" and arg:
            abort(arg)
        elif cmd == "/modifica" and arg:
            change = text.split(maxsplit=2)[2] if len(parts) > 2 else ""
            if not change: raise RuntimeError("Scrivi la correzione dopo l'episodio, es. /modifica EP027 la tuta si colora su tutte le gambe")
            episodes.request_for(arg)
            telegram.send(f"<b>{arg}</b> · preparo la modifica…")
            run_job("proposta", arg, do_revise, arg, change)
        elif cmd == "/brainstorming":
            idea = text.split(maxsplit=1)[1] if len(parts) > 1 else ""
            brain_close(); brain_save({"history": [], "started": datetime.datetime.now().isoformat(timespec="seconds")})
            if idea: run_job("brainstorming", "IDEA", do_brainstorm, "IDEA", idea)
            else: telegram.send("Raccontami l'idea, anche abbozzata: scrivi pure senza comandi. "
                                "Ti rispondo con titolo e descrizione da confermare. Chiudi con /fine.")
        elif cmd == "/fine":
            brain_close(); telegram.send("Brainstorming chiuso.")
        elif cmd == "/idee":
            tema = text.split(maxsplit=1)[1] if len(parts) > 1 else ""
            telegram.send("Cerco idee nuove…"); run_job("idee", "IDEE", do_ideas, "IDEE", tema)
        elif cmd == "/nuovo":
            idea = text.split(maxsplit=1)[1] if len(parts) > 1 else ""
            if not idea: raise RuntimeError("Scrivi l'idea dopo il comando, es. /nuovo pozzanghere colorate su Marte")
            ep_new = writer.next_id()
            telegram.send(f"<b>{ep_new}</b> · scrivo la proposta…")
            run_job("proposta", ep_new, do_propose, ep_new, idea)
        elif cmd in ("/programma", "/pianifica") and arg:
            # /programma EP026 20/10 17:30   oppure   /programma EP026 2026-10-20 17:30   oppure   /programma EP026 coda
            st = state(arg); ready = [k for k, v in st["takes"].items() if v.get("final_url")]
            if not ready: raise RuntimeError(f"{arg} non ha ancora un finale approvato")
            take = int(ready[-1]); rest = parts[2:]
            if not rest or rest[0].lower() == "coda":
                run_job("schedule", arg, do_schedule, arg, take, None, None)
            else:
                d = rest[0]; hm = rest[1] if len(rest) > 1 else "17:30"
                now = datetime.datetime.now()
                if "/" in d:
                    dd, mm = d.split("/")[:2]; y = now.year
                    dt = datetime.datetime(y, int(mm), int(dd), *map(int, hm.split(":")))
                    if dt < now: dt = dt.replace(year=y + 1)
                else:
                    dt = datetime.datetime.fromisoformat(f"{d}T{hm}")
                from zoneinfo import ZoneInfo
                due = dt.replace(tzinfo=ZoneInfo("Europe/Rome")).isoformat()
                run_job("schedule", arg, do_schedule, arg, take, due, "customScheduled")
        elif cmd == "/episodi":
            _, eps = episodes.all_episodes()
            telegram.send("\n".join(f"{k} · {v['title']} ({v['duration']}s) · take {len(state(k)['takes'])}" for k, v in sorted(eps.items())))
        elif cmd == "/costi":
            telegram.send(costs.report(arg or None))
        else:
            telegram.send("Comandi:\n/episodi — elenco episodi\n/nuovo idea — propone un episodio nuovo\n/idee tema — 5 idee pronte, ispirate agli episodi esistenti\n/brainstorming idea — ragioniamo insieme su un'idea abbozzata (chiudi con /fine)\n/bozza EP027 — genera la bozza\n/upscale EP027 — prova l'upscale fal della bozza (take: /upscale EP027 2)\n/annulla EP027 — esce dalla produzione dell'episodio\n/modifica EP027 correzione — corregge l'episodio e rifà la bozza\n/stato EP027 — stato\n/programma EP026 20/10 17:30 — programma su Buffer (ora italiana)\n/programma EP026 coda — mette in coda Buffer\n/costi — spese della settimana per episodio (/costi EP028 per il dettaglio)\n/id — chat id")
    except Exception as e:
        telegram.send(f"⚠️ {telegram.esc(e)}")
    return {"ok": True}
