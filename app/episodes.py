"""Episodi: definizioni (channels/<canale>/eps.py + eventuali episodi aggiunti via API) e richiesta Seedance."""
import importlib.util, json, re
from . import config

SUPA_REFS = f"{config.SUPABASE_URL}/storage/v1/object/public/{config.SUPABASE_REFS_BUCKET}/"
CH_DIR = config.APP / "channels" / config.CHANNEL


def _eps_module():
    spec = importlib.util.spec_from_file_location("eps", CH_DIR / "eps.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def channel():
    return json.loads((CH_DIR / "channel.json").read_text(encoding="utf-8"))


def extra_file():
    f = config.DATA / config.CHANNEL / "episodes_extra.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    return f


def all_episodes():
    m = _eps_module()
    eps = dict(m.EPISODES)
    f = extra_file()
    if f.exists():
        eps.update(json.loads(f.read_text(encoding="utf-8")))
    return m, eps


def define(ep_id, spec: dict):
    """Aggiunge/sovrascrive un episodio senza ridistribuire il codice (stessi campi di eps.py)."""
    need = {"title", "slug", "duration", "cast", "world", "action", "rules", "audio", "title_it", "title_en"}
    miss = need - set(spec)
    if miss: raise ValueError(f"Campi mancanti: {sorted(miss)}")
    f = extra_file(); data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    data[ep_id] = spec; f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def request_for(ep_id, draft=True):
    m, eps = all_episodes()
    if ep_id not in eps: raise KeyError(f"Episodio {ep_id} non definito")
    m.EPISODES[ep_id] = eps[ep_id]
    E, sections, refs = m.build(ep_id)
    prompt = "\n\n".join(t for _, t in sections)
    n_img = len(set(re.findall(r"@Image(\d+)", prompt)))
    if n_img != len(refs): raise ValueError(f"Il prompt usa {n_img} @Image ma ci sono {len(refs)} riferimenti")
    last = max(int(x) for x in re.findall(r"-(\d+)s:", prompt))
    if last != E["duration"]: raise ValueError(f"Le azioni arrivano a {last}s ma duration = {E['duration']}")
    req = {"model": "bytedance/seedance-2-5", "input": {
        "prompt": prompt, "reference_image_urls": [SUPA_REFS + f for *_, f in refs],
        "reference_video_urls": None, "reference_audio_urls": None, "generate_audio": True,
        "resolution": "480p" if draft else "1080p", "aspect_ratio": E.get("aspect", "9:16"), "duration": E["duration"],
        "output_format": "mp4", "web_search": False, "draft": bool(draft), "nsfw_checker": True}}
    return E, req


def shots(E):
    out = []
    for i, a in enumerate(E["action"], 1):
        mm = re.match(r"\s*(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)s", a)
        if mm: out.append(dict(id=f"S{i:02d}", t0=float(mm[1]), t1=float(mm[2]), text=a[mm.end():].strip(" :")))
    return out


def texts(ep_id):
    """Titolo e descrizione per YouTube/Buffer (IT principale; EN da aggiungere come traduzione in Studio)."""
    _, eps = all_episodes(); E = eps[ep_id]; ch = channel()
    d_it = E.get("desc_it", "").strip(); d_en = E.get("desc_en", "").strip()
    return dict(title_it=E["title_it"], title_en=E["title_en"],
                description_it=(d_it + "\n" if d_it else "") + ch["description_tail_it"],
                description_en=(d_en + "\n" if d_en else "") + ch["description_tail_en"])
