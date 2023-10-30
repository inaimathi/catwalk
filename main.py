import asyncio
import json
import os
import re
import subprocess
import threading

import tornado
import tqdm

import basics
import blogcast.script
import tts
import util

if not os.path.exists("static"):
    os.makedirs("static")

GPU = asyncio.Semaphore(1)

if os.path.exists("))blacklist.txt"):
    with open("blacklist.txt", 'r') as f:
        IP_BLACKLIST = set(f.read().splitlines())
else:
    IP_BLACKLIST = set([])

def _BAN(ip):
    print(f"BANNING {ip}...")
    with open("blacklist.txt", 'a+') as bl:
        bl.write(f"{ip}\n")
    IP_BLACKLIST.add(ip)

class JSONHandler(tornado.web.RequestHandler):
    SUPPORTED_METHODS = tornado.web.RequestHandler.SUPPORTED_METHODS + ('CONNECT',)
    def prepare(self):
        if self.request.remote_ip in IP_BLACKLIST:
            self.json({"status": "whoops"}, 403)

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

    def connect(self):
        _BAN(self.request.remote_ip)
        self.json({"status": "looks like you're going to the shadow realm, Jimbo"}, 400)

    def json(self, data, status=None):
        if status is not None:
            self.set_status(status)
        self.write(json.dumps(data))

class TrapCard(JSONHandler):
    def prepare(self):
        if self.request.remote_ip in IP_BLACKLIST:
            return self.json({"status": "whoops"}, 403)
        _BAN(self.request.remote_ip)
        self.json({"status": "looks like you're going to the shadow realm, Jimbo"}, 400)
        return


class HealthHandler(JSONHandler):
    def get(self):
        val = self.get_argument("value", None)
        res = {"status": "ok"}
        if val is not None:
            res["value"] = val
        self.json(res)

class TranscribeHandler(JSONHandler):
    async def post(self):
        if 'file' not in request.files:
            return self.json({"status": "error", "message": "request must have a file"}, 400)
        file = self.request.files['file'][0]
        if file['filename'] == '':
            return self.json({"status": "error", "message": "request must have a file"}, 400)
        allowed_extensions = {".wav", ".mp3"}
        if not os.path.splitext(file['filename'])[1].lower() in allowed_extensions:
            return self.json({
                "status": "error",
                "message": f"file must be one of {', '.join(allowed_extensions)}"
            }, 400)

        with open(util.fresh_file("tmp-transcription-audio-", os.path.splitext(file.filename)), 'wb') as out:
            out.write(file['body'])

        async with GPU:
            return jsonify({"status": "ok", "result": basics.transcribe(path)})


class TTSHandler(JSONHandler):
    def get(self):
        self.json({
            "voices": tts.get_voices()
        })

    async def post(self):
        text = self.get_argument('text')
        if text is None:
            return self.json({"status": "error", "message": "request must have text"}, 400)

        voice = self.get_argument("voice", "leo")
        k = int(self.get_argument("k", "1"))

        async with GPU:
            res = tts.text_to_wavs(text, voice, k)

        self.json({
            "status": "ok", "voice": voice, "text": text,
            "urls": [f"/static/{os.path.basename(r)}" for r in res]
        })


class BlogcastHandler(JSONHandler):
    async def post(self):
        url = self.get_argument('url')
        if url is None:
            return self.json({"status": "error", "message": "request must have a target URL"}, 400)

        voice = self.get_argument("voice", "leo")

        async with GPU:
            script = blogcast.script.script_from(url)

        res = []
        for el in tqdm.tqdm(script):
            if isinstance(el, str):
                async with GPU:
                    res_tts = tts.text_to_wavs(el, voice, 1)
                res.append({
                    "text": el,
                    "url": f"/static/{os.path.basename(res_tts[0])}"
                })
            else:
                res.append(el)

        self.json({
            "status": "ok", "voice": voice, "target": url,
            "result": res
        })


class ChatHandler(JSONHandler):
    def post():
        return self.json({"status": "ok", "stub": "TODO"})

class TextCompletionHandler(JSONHandler):
    async def post():
        prompt = self.get_argument("prompt")
        if prompt is None:
            return self.json({"status": "error", "message": "request must have prompt"}, 400)

        max_new_tokens = self.get_argument("max_new_tokens")

        async with GPU:
            return self.json({"status": "ok", "result": basics.generate_text(prompt, max_new_tokens)})

class DescribeImageHandler(JSONHandler):
    async def post():
        url = self.get_argument("url")
        if url is None:
            self.json({"status": "error", "message": "request must have url"}, 400)

        async with GPU:
            return self.json({"status": "ok", "result": basics.caption_image(url)})


ROUTES = [
    (r"/v0/health", HealthHandler),
    (r"/v0/audio/tts", TTSHandler),
    (r"/v0/audio/blogcast", BlogcastHandler),
    (r"/v0/audio/transcribe", TranscribeHandler),
    (r"/v0/text/chat", TranscribeHandler),
    (r"/v0/text/generate", TextCompletionHandler),
    (r"/v0/image/describe", DescribeImageHandler),
    (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": f"{os.getcwd()}/static"})
]

def serve_static(port):
    print(f"Serving static directory on {port}...")
    subprocess.run(["python", "-m", "http.server", "-d", "static", port])

THREAD = None

async def main(port, static_port):
    global THREAD
    print("Setting up app...")
    app = tornado.web.Application(
        ROUTES,
        default_handler_class=TrapCard
    )
    THREAD = threading.Thread(target=serve_static, args=(static_port,), daemon=True)
    THREAD.start()
    print(f"  listening on {port}...")
    app.listen(port)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main(8080, 8081))
