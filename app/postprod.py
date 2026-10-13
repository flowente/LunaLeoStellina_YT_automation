"""Post-produzione del canale: color grade + numeri/scritte (overlay) + bagliori (glow) + loop + audio -14 LUFS.
Stessa logica della pipeline locale (_shared/pipeline/postprod.py), ma i parametri arrivano dall'episodio e da channel.json."""
import json, re, shutil, subprocess
from pathlib import Path
import cv2, numpy as np
from . import config


def ffmpeg():
    return shutil.which("ffmpeg") or "ffmpeg"


def overlay_filter(items) -> str:
    """items: [[testo, da_s, a_s, posizione?], ...]  posizione = "row" | "center" | [x, y] | {"y":..,"x":[[t,x],...]}"""
    parts = []
    for item in items or []:
        text, t0, t1 = item[:3]; pos = item[3] if len(item) > 3 else "row"; y = "h*0.20"
        if isinstance(pos, dict):
            k = pos["x"]; ex = f"{k[-1][1]}"
            for (ta, xa), (tb, xb) in reversed(list(zip(k, k[1:]))):
                ex = f"if(lt(t,{tb}),{xa}+({xb}-{xa})*(t-{ta})/({tb}-{ta}),{ex})"
            ex = f"if(lt(t,{k[0][0]}),{k[0][1]},{ex})"
            x = f"w*({ex})-text_w/2"; y = f"h*{pos['y']}-text_h/2"
        elif isinstance(pos, list):
            x = f"w*{pos[0]}-text_w/2"; y = f"h*{pos[1]}-text_h/2"
        elif pos == "center":
            x = "(w-text_w)/2"; y = "h*0.36"
        else:
            idx = int(text) - 1 if str(text).isdigit() else 1
            x = f"(w*{0.25 + 0.25 * (idx % 3):.2f})-text_w/2"
        parts.append(f"drawtext=fontfile=Poppins-Bold.ttf:text='{text}':fontsize=h*0.085:fontcolor=white:"
                     f"borderw=8:bordercolor=0x3D4466:x='{x}':y='{y}':enable='between(t,{t0},{t1})'")
    return ("," + ",".join(parts)) if parts else ""


def loudnorm_2pass(video: Path, p: dict) -> str:
    base = f"loudnorm=I={p['loudness_lufs']}:TP={p['true_peak_db']}:LRA=11"
    try:
        r = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(video), "-af", base + ":print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True, check=True)
        m = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
        return (base + f":measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
                f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    except Exception:
        return base


def size(video: Path):
    info = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(video)], capture_output=True, text=True).stderr
    return map(int, re.search(r"Video:.*?(\d{3,5})x(\d{3,5})", info).groups())


def video_args(video: Path, vf: str, pulses) -> list:
    """Bagliori in modalità 'screen' (schiariscono senza coprire). pulses: [[t_picco, x, y, diametro], ...]"""
    if not pulses: return ["-vf", vf]
    W, H = size(video); g = [f"[0:v]{vf},format=gbrp[b0]"]
    for i, (t, x, y, sz) in enumerate(pulses):
        rad = "pow(max(0,1-hypot(X-W/2,Y-H/2)/(W/2)),1.6)"
        g.append(f"color=c=black:s=96x96:d=60,format=gbrp,geq=r='255*{rad}':g='214*{rad}':b='110*{rad}',"
                 f"fade=t=in:st={t-0.15:.2f}:d=0.15,fade=t=out:st={t+0.05:.2f}:d=0.45[gs{i}]")
        d = int(W * sz) // 2 * 2
        g += [f"[gs{i}]scale={d}:{d}[gr{i}]", f"color=c=black:s={W}x{H}:d=60,format=gbrp[cv{i}]",
              f"[cv{i}][gr{i}]overlay=x={W}*{x}-w/2:y={H}*{y}-h/2[gl{i}]", f"[b{i}][gl{i}]blend=all_mode=screen:shortest=1[b{i+1}]"]
    g.append(f"[b{len(pulses)}]format=yuv420p[vout]")
    return ["-filter_complex", ";".join(g), "-map", "[vout]", "-map", "0:a?"]


def loop_end(video: Path, search_s: float = 1.5) -> float:
    """Fine del video sul fotogramma più simile al primo (loop invisibile)."""
    c = cv2.VideoCapture(str(video)); fps = c.get(cv2.CAP_PROP_FPS) or 24; fs = []
    while True:
        ok, f = c.read()
        if not ok: break
        fs.append(cv2.cvtColor(cv2.resize(f, (240, 427)), cv2.COLOR_BGR2GRAY))
    n = len(fs); first = fs[0].astype(np.int16); lo = max(1, n - int(search_s * fps))
    best = min(range(lo, n), key=lambda i: float(np.abs(fs[i].astype(np.int16) - first).mean()))
    return best / fps


def finalize(video: Path, E: dict, post: dict) -> Path:
    video = Path(video); out = video.with_name(video.stem + "_final.mp4")
    cut = None
    if E.get("loop_end_s"): cut = float(E["loop_end_s"])
    elif post.get("loop_auto") and not E.get("no_loop"): cut = loop_end(video)
    vf = post["color_grade"] + overlay_filter(E.get("overlay"))
    af = loudnorm_2pass(video, post) + (f",afade=t=out:st={cut-0.05:.3f}:d=0.05" if cut else "")
    cmd = [ffmpeg(), "-v", "error", "-y", "-i", str(video), *(["-t", f"{cut:.3f}"] if cut else []),
           *video_args(video, vf, E.get("glow")), "-af", af,
           "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, cwd=config.FONTS)
    return out


def frame(video: Path, t: float, out: Path) -> Path:
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-ss", f"{t}", "-i", str(video), "-frames:v", "1", str(out)], check=True)
    return out
