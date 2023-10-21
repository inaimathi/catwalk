import json
import os
import subprocess
import tempfile

import requests

import util

SERVER = "http://192.168.0.12:8080"

def get(endpoint, version="v0"):
    return requests.get(f"{SERVER}/{version}/{endpoint}")

def post(endpoint, data=None, version="v0", files=None):
    return requests.post(f"{SERVER}/{version}/{endpoint}", data=data, files=files)

def download(fname, url):
    resp = requests.get(url)
    with open(fname, 'wb') as f:
        f.write(resp.content)
    return fname

def download_post(sub_dir, script):
    if not os.path.isdir(sub_dir):
        os.mkdir(sub_dir)
    res = []
    for el in script:
        if 'file' in el:
            fname = os.path.basename(el['file'])
            res.append(download(f"{sub_dir}/{fname}", f"{SERVER}/static/{fname}"))
    return res

def health():
    return request.get(f"{SERVER}/health").json()

def transcribe(audio_fname):
    with open(audio_fname, 'rb') as f:
        res = post("audio/transcribe", files={"file": f})
    return res

def tts(text, voice=None, k=1):
    data = {"text": text, "k": k}
    if voice is not None:
        data["voice"] = voice
    resp = post(f"audio/tts", data=data)
    if resp.status_code == 200:
        urls = resp.json()['urls']
        return [download(os.path.basename(url), f"{SERVER}{url}") for url in urls]
    return resp

def blogcast(url, voice=None, k=1):
    data = {"url": url}
    if voice is not None:
        data["voice"] = voice
    res = post("audio/blogcast", data=data)
    print(res)
    dir = tempfile.mkdtemp(prefix=os.path.basename(url))
    with open(f"{dir}/result.json", 'w') as f:
        json.dump(res, f)
    for ix, el in enumerate(res.json()["result"]):
        furl = el.get('url')
        if furl is not None:
            fname = os.path.basename(furl)
            download(f"{dir}/{str(ix).zfill(6)}-{fname}", f"{SERVER}{furl}")
    return dir


def _llama_msg(msg):
    if msg["role"] == "user":
        return f"[INST]{msg['content']}[/INST]"
    else:
        return msg['content']

def _llama_chat(messages):
    if isinstance(messages, str):
        return messages
    return "\n".join(_llama_msg(m) for m in messages)


def llama(prompt, target="http://192.168.0.16:5000"):
    resp = requests.post(
        f"{target}/predictions",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"input": {"prompt": _llama_chat(prompt), "max_new_tokens": "1800"}})
    )
    if resp.status_code == 200:
        return "".join(resp.json()["output"]).strip()
    return resp
