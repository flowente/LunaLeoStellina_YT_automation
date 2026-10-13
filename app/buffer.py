"""Buffer (API GraphQL): programma lo short sul canale YouTube con titolo, descrizione e impostazioni per bambini."""
import requests
from . import config, episodes

MUTATION = """mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id status dueAt } }
    ... on MutationError { message }
  }
}"""


def schedule(ep_id: str, video_url: str, due_at: str | None = None, mode: str | None = None, thumbnail_offset_ms: int | None = None):
    if not config.BUFFER_API_KEY: raise RuntimeError("BUFFER_API_KEY non impostata")
    ch = episodes.channel(); t = episodes.texts(ep_id)
    yt = dict(ch["buffer_youtube"]); yt["title"] = t["title_it"][:100]
    video = {"url": video_url}
    if thumbnail_offset_ms is not None: video["metadata"] = {"thumbnailOffset": int(thumbnail_offset_ms)}
    inp = {"channelId": ch["buffer_channel_id"], "schedulingType": "automatic",
           "mode": mode or ("customScheduled" if due_at else "addToQueue"),
           "text": t["description_it"], "assets": [{"video": video}], "metadata": {"youtube": yt}}
    if due_at: inp["dueAt"] = due_at
    r = requests.post(config.BUFFER_API_URL, json={"query": MUTATION, "variables": {"input": inp}},
                      headers={"Authorization": f"Bearer {config.BUFFER_API_KEY}"}, timeout=120)
    r.raise_for_status(); j = r.json()
    if j.get("errors"): raise RuntimeError(f"Buffer: {j['errors']}")
    res = j["data"]["createPost"]
    if "post" not in res: raise RuntimeError(f"Buffer: {res.get('message')}")
    return res["post"]
