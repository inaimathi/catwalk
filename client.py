import os
import subprocess

import requests

SERVER = "http://192.168.0.16:8080"

def download(fname, url):
    resp = requests.get(url)
    with open(fname, 'wb') as f:
        f.write(resp.content)
    return fname

def play(fname):
    subprocess.check_output(["mplayer", fname])

def tts(text, voice=None, k=1):
    data = {"text": text, "k": k}
    if voice is not None:
        data["voice"] = voice
    resp = requests.post(f"{SERVER}/v0/audio/tts", data=data)
    if resp.status_code == 200:
        urls = resp.json()['urls']
        return [download(os.path.basename(url), f"{SERVER}{url}") for url in urls]
    return resp

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
