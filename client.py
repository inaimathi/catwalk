import glob
import json
import os
import subprocess
import tempfile

import requests

import util

SERVER = "http://192.168.0.12:8080"

def _subport(port):
    return ":".join(SERVER.split(":")[:-1] + [str(port)])

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
    return get("health").json()

def transcribe(audio_fname):
    with open(audio_fname, 'rb') as f:
        res = post("audio/transcribe", files={"file": f})
    return res

def image(prompt):
    data = {"prompt": prompt}
    resp = post(f"image/from_prompt", data=data)
    if resp.status_code == 200:
        url = resp.json()['url']
        port = resp.json()['port']
        return download(os.path.basename(url), f"{_subport(port)}{url}")
    return resp

def tts(text, voice=None, k=1):
    data = {"text": text, "k": k}
    if voice is not None:
        data["voice"] = voice
    resp = post(f"audio/tts", data=data)
    if resp.status_code == 200:
        urls = resp.json()['urls']
        port = resp.json()['port']
        return [download(os.path.basename(url), f"{_subport(port)}{url}") for url in urls]
    return resp

def blogcast(url, voice=None, k=1):
    data = {"url": url}
    if voice is not None:
        data["voice"] = voice
    res = post("audio/blogcast", data=data)
    down_dir = tempfile.mkdtemp(prefix=f"{os.path.basename(url)}-", dir=".")
    with open(f"{down_dir}/result.json", 'w') as f:
        json.dump(res.json(), f, indent=2)
    port = res.json()['port']
    for ix, el in enumerate(res.json()["result"]):
        furl = el.get('url')
        if furl is not None:
            fname = os.path.basename(furl)
            download(f"{down_dir}/{str(ix).zfill(6)}-{fname}", f"{_subport(port)}{furl}")
    return sorted(glob.glob(f"{down_dir}/*wav"))

def multi_blogcast(urls, voice=None, dest_list=None):
    for url in urls:
        print(f"Casting {url}...")
        res = blogcast(url, voice=voice)
        if dest_list is not None:
            dest_list.append(res)
