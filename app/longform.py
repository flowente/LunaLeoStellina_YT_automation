"""Video lunghi: un video lungo (LV001…) è una sequenza di capitoli, ogni capitolo una lista di clip.
Ogni clip è un episodio normale (eps.py, di solito 16:9) e passa dalla pipeline degli short: bozza -> Approva (upscale) -> finale.
Qui: definizioni, tabellone, bozze in serie con tetto di spesa, montaggio (dissolvenze, musica, capitoli YouTube, miniatura)."""
import hashlib, hmac, json, subprocess, time
from pathlib import Path
import requests
from . import config, episodes, postprod, storage

LONG_FILE = config.APP / "channels" / config.CHANNEL / "longs.json"
EST_DRAFT_USD = 2.05          # bozza 480p 12 s ($1,68) + giudice OpenAI (≈ $0,37)
EST_FINAL_USD = 0.55          # upscale fal di una clip
XFADE = 0.35                  # secondi di dissolvenza tra una clip e l'altra
CLIP_AUDIO = 0.35             # volume di effetti e risatine delle clip sotto la musica


def all_longs() -> dict:
    return json.loads(LONG_FILE.read_text(encoding="utf-8")) if LONG_FILE.exists() else {}


def get(lv: str) -> dict:
    L = all_longs()
    if lv not in L: raise KeyError(f"Video lungo {lv} non definito")
    return L[lv]


def clips(L: dict) -> list:
    return [c for ch in L["chapters"] for c in ch["clips"]]


def long_dir(lv):
    d = config.DATA / config.CHANNEL / "long" / lv; d.mkdir(parents=True, exist_ok=True); return d


# ------------------------------------------------------------------ stato delle clip
def clip_status(clip: str, state_fn) -> dict:
    """defined / drafted / final, più la take migliore. state_fn = main.state"""
    _, eps = episodes.all_episodes()
    st = state_fn(clip); takes = st.get("takes", {})
    final_take = next((k for k in sorted(takes, key=int, reverse=True) if takes[k].get("final_url")), None)
    return {"defined": clip in eps, "drafts": len(takes), "final_take": final_take,
            "pending": bool(st.get("pending")), "title": eps.get(clip, {}).get("title", "")}


def board(lv: str, state_fn) -> str:
    L = get(lv); lines = [f"<b>{lv} · {L['title']}</b>  ({L.get('aspect', '16:9')})"]
    tot = fin = 0
    for ch in L["chapters"]:
        lines.append(f"\n<b>{ch['title']}</b>")
        for c in ch["clips"]:
            s = clip_status(c, state_fn); tot += 1
            if s["final_take"]: icon = "✅"; fin += 1
            elif s["pending"]: icon = "⏳"
            elif s["drafts"]: icon = "🟡"
            elif s["defined"]: icon = "⚪"
            else: icon = "✏️"
            lines.append(f"{icon} {c} {s['title']}" + (f" · {s['drafts']} bozze" if s["drafts"] else ""))
    todo = tot - fin
    lines.append(f"\n{fin}/{tot} clip pronte. Legenda: ✅ finale · 🟡 bozza da approvare · ⏳ in lavorazione · ⚪ da generare · ✏️ da scrivere")
    lines.append(f"Spesa stimata per finire: ≈ ${todo * (EST_DRAFT_USD + EST_FINAL_USD):.0f} (senza rifacimenti)")
    return "\n".join(lines)


# ------------------------------------------------------------------ bozze in serie
def batch_drafts(lv: str, budget: float, do_draft, state_fn, notify_text, log):
    """Genera, una alla volta, le bozze delle clip definite che non ne hanno ancora. Si ferma prima di superare il tetto."""
    L = get(lv); spent = 0.0; done = []; skipped = []
    for c in clips(L):
        s = clip_status(c, state_fn)
        if not s["defined"]: skipped.append(f"{c} (da scrivere)"); continue
        if s["drafts"] or s["final_take"] or s["pending"]: continue
        if spent + EST_DRAFT_USD > budget:
            notify_text(f"<b>{lv}</b> · tetto di ${budget:.0f} raggiunto dopo {len(done)} bozze (≈ ${spent:.2f}). "
                        f"Rilancia <code>/lungo bozze {lv} {budget:.0f}</code> per continuare."); break
        log(f"bozza {c}"); do_draft(c, log=log); spent += EST_DRAFT_USD; done.append(c)
    else:
        notify_text(f"<b>{lv}</b> · bozze in serie finite: {len(done)} nuove (≈ ${spent:.2f})."
                    + (f"\nDa scrivere: {', '.join(skipped)}" if skipped else ""))
    return {"lv": lv, "drafts": done, "spent_est": round(spent, 2), "skipped": skipped}


# ------------------------------------------------------------------ montaggio
def _run(cmd):
    subprocess.run(cmd, check=True)


def _dur(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def final_file(clip: str, state_fn, ep_dir_fn) -> Path:
    """Il file finale della clip: sul volume se c'è, altrimenti scaricato dal link pubblico."""
    st = state_fn(clip); takes = st.get("takes", {})
    for k in sorted(takes, key=int, reverse=True):
        t = takes[k]
        if not t.get("final_url"): continue
        local = ep_dir_fn(clip) / "renders" / Path(t.get("final_1080") or t["final_url"]).name
        if not local.exists(): storage_download(t["final_url"], local)
        return local
    # episodi fatti prima del volume: prova i nomi standard su Supabase
    base = f"{config.SUPABASE_VIDEO_PREFIX}/{config.CHANNEL}/{clip}/"
    for name in (f"{clip}_take01_1080p_up_final.mp4", f"{clip}_take01_1080p_final.mp4"):
        url = storage.public_url(base + name)
        if requests.head(url, timeout=30).status_code == 200:
            local = ep_dir_fn(clip) / "renders" / name
            if not local.exists(): storage_download(url, local)
            return local
    raise RuntimeError(f"{clip}: nessun finale (approva la bozza prima di montare)")


def storage_download(url, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20): f.write(chunk)


def _normalize(src: Path, dst: Path, W: int, H: int):
    """Stessa risoluzione, 24 fps, audio stereo 48 kHz. Le clip verticali (short) finiscono al centro su sfondo sfocato."""
    sw, sh = map(int, subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                                      "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout.strip().split(",")[:2])
    if (sw > sh) == (W > H):          # stesso orientamento: solo scala (veloce)
        vf = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps=24,format=yuv420p,setsar=1"
    else:                             # short verticale in un video orizzontale: al centro su sfondo sfocato
        vf = (f"split[a][b];[a]scale={W // 4}:{H // 4}:force_original_aspect_ratio=increase,crop={W // 4}:{H // 4},boxblur=8:3,scale={W}:{H}[bg];"
              f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,fps=24,format=yuv420p,setsar=1")
    _run([postprod.ffmpeg(), "-v", "error", "-y", "-i", str(src), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
          "-filter_complex", f"[0:v]{vf}[v];[0:a]aresample=48000,aformat=channel_layouts=stereo[a0];[a0][1:a]amix=inputs=2:duration=first:normalize=0[a]",
          "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k",
          "-shortest", str(dst)])


def _fmt(t: float) -> str:
    t = int(round(t)); return f"{t // 60}:{t % 60:02d}"


def montage(lv: str, state_fn, ep_dir_fn, log) -> dict:
    L = get(lv); d = long_dir(lv); W, H = (1920, 1080) if L.get("aspect", "16:9") == "16:9" else (1080, 1920)
    parts, starts, t = [], [], 0.0
    for ch in L["chapters"]:
        first = True
        for c in ch["clips"]:
            src = final_file(c, state_fn, ep_dir_fn); n = d / f"n_{len(parts):02d}_{c}.mp4"
            log(f"normalizzo {c}"); _normalize(src, n, W, H)
            dur = _dur(n)
            if first: starts.append((ch["title"], t)); first = False
            parts.append((n, dur)); t += dur - XFADE
    if len(parts) < 2: raise RuntimeError("servono almeno 2 clip per il montaggio")
    # catena di dissolvenze video (xfade) e audio (acrossfade)
    inputs = sum((["-i", str(p)] for p, _ in parts), [])
    fv, fa, off = [], [], 0.0; lv_, la_ = "[0:v]", "[0:a]"
    for i in range(1, len(parts)):
        off += parts[i - 1][1] - XFADE
        ov, oa = (f"[v{i}]", f"[a{i}]")
        fv.append(f"{lv_}[{i}:v]xfade=transition=fade:duration={XFADE}:offset={off:.3f}{ov}")
        fa.append(f"{la_}[{i}:a]acrossfade=d={XFADE}{oa}")
        lv_, la_ = ov, oa
    total = off + parts[-1][1]
    music = L.get("music")
    if music:
        mpath = d / Path(music).name
        if not mpath.exists(): storage_download(storage.public_url(music) if not music.startswith("http") else music, mpath)
        inputs += ["-stream_loop", "-1", "-i", str(mpath)]; mi = len(parts)
        fa.append(f"{la_}volume={CLIP_AUDIO}[cl];[{mi}:a]atrim=0:{total:.3f},afade=t=in:d=1,afade=t=out:st={max(total - 2.5, 0):.3f}:d=2.5[mu];"
                  f"[cl][mu]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
    else:
        fa.append(f"{la_}loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
    out = d / f"{lv}_final.mp4"
    log("montaggio finale")
    _run([postprod.ffmpeg(), "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fv + fa),
          "-map", lv_, "-map", "[aout]", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)])
    preview = d / f"{lv}_anteprima_480p.mp4"
    _run([postprod.ffmpeg(), "-v", "error", "-y", "-i", str(out), "-vf", f"scale=-2:{480 if W > H else 854}",
          "-c:v", "libx264", "-crf", "30", "-preset", "fast", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(preview)])
    cover_t = float((L.get("cover") or {}).get("t", min(20.0, total / 3)))
    cover = d / f"{lv}_miniatura_1280x720.png"
    _run([postprod.ffmpeg(), "-v", "error", "-y", "-ss", f"{cover_t}", "-i", str(out), "-frames:v", "1",
          "-vf", "scale=1280:720" if W > H else "scale=720:1280", str(cover)])
    # capitoli YouTube: il primo a 0:00, almeno 3, ognuno di almeno 10 s
    chap = [f"{_fmt(s)} {title}" for title, s in starts]
    ok_chap = len(starts) >= 3 and all(b[1] - a[1] >= 10 for a, b in zip(starts, starts[1:])) and (total - starts[-1][1]) >= 10
    for p, _ in parts: p.unlink(missing_ok=True)
    return {"lv": lv, "file": out, "preview": preview, "cover": cover, "duration": round(total, 1),
            "chapters": chap if ok_chap else [], "size_mb": round(out.stat().st_size / 1e6, 1)}


def texts(lv: str, chapters: list) -> dict:
    L = get(lv); ch = episodes.channel()
    desc = L.get("desc_it", "").strip()
    if chapters: desc += "\n\n" + "\n".join(chapters)
    return {"title_it": L["title_it"], "title_en": L.get("title_en", ""), "description_it": desc + "\n\n" + ch["description_tail_it"]}


# ------------------------------------------------------------------ link privato a tempo (il file è troppo grande per Supabase gratuito)
def _sig(lv, name, exp):
    return hmac.new(config.SERVICE_TOKEN.encode(), f"{lv}/{name}/{exp}".encode(), hashlib.sha256).hexdigest()[:32]


def signed_path(lv: str, name: str, hours: int = 72) -> str:
    exp = int(time.time()) + hours * 3600
    return f"/pub/{lv}/{name}?exp={exp}&sig={_sig(lv, name, exp)}"


def check_sig(lv, name, exp, sig) -> bool:
    try: return int(exp) > time.time() and hmac.compare_digest(sig, _sig(lv, name, int(exp)))
    except Exception: return False
