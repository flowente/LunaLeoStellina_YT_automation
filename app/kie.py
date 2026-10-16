"""Kie AI / Seedance 2.5: crea il task, aspetta, scarica. Il credito si legge prima e dopo per il registro costi."""
import json, time
import requests
from . import config

H = lambda: {"Authorization": f"Bearer {config.KIE_API_KEY}", "Content-Type": "application/json"}


def _data(r):
    j = r.json()
    if j.get("code") != 200:                       # Kie risponde HTTP 200 anche in errore: il codice è nel body
        raise RuntimeError(f"Kie {j.get('code')}: {j.get('msg')}")
    return j["data"]


def credit():
    try:
        return float(_data(requests.get(f"{config.KIE_API}/api/v1/chat/credit", headers=H(), timeout=30)))
    except Exception:
        return None


def create(req):
    return _data(requests.post(f"{config.KIE_API}/api/v1/jobs/createTask", headers=H(), json=req, timeout=60))["taskId"]


def wait(task, timeout_s=30 * 60, log=print):
    t0, w = time.time(), 10
    while True:
        time.sleep(w); w = min(w + 5, 30)
        d = _data(requests.get(f"{config.KIE_API}/api/v1/jobs/recordInfo", headers=H(), params={"taskId": task}, timeout=60))
        log(f"{int(time.time() - t0)}s · {d.get('state')}")
        if d.get("state") == "success":
            return json.loads(d["resultJson"])["resultUrls"][0], d
        if d.get("state") == "fail":
            raise RuntimeError(f"Kie fallito: {d.get('failCode')} {d.get('failMsg')} (nessun credito addebitato)")
        if time.time() - t0 > timeout_s:
            raise TimeoutError(f"Task {task} ancora in corso")


def upgrade_request(draft_task_id):
    """Bozza approvata -> 1080p: stesso identico video."""
    return {"model": "bytedance/seedance-2-5-draft",
            "input": {"draft_task_id": draft_task_id, "resolution": "1080p", "output_format": "mp4", "nsfw_checker": True}}


def download(url, path):
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20): f.write(chunk)
    return path
