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

def tts(text, voice=None):
    resp = requests.post(f"{SERVER}/v0/audio/tts", data={"text": text})
    if resp.status_code == 200:
        url = resp.json()['url']
        return download(os.path.basename(url), f"{SERVER}{url}")
    return resp
