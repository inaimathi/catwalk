import asyncio
import json
import os

import tornado
import tqdm

import basics
import blogcast.script
import tts
import util

if not os.path.exists("static"):
    os.makedirs("static")

GPU = asyncio.Semaphore(1) # TODO replace with asyncio.Semaphore(some_number) once I get a better GPU :p

########## Blacklist
if os.path.exists("))blacklist.txt"):
    with open("blacklist.txt", 'r') as f:
        IP_BLACKLIST = set(f.read().splitlines())
else:
    IP_BLACKLIST = set([])

class TrapCard(JSONHandler):
    def prepare(self):
        with open("blacklist.txt", 'a+') as bl:
            bl.write(f"{ip}\n")
        IP_BLACKLIST.add(ip)
        self.set_status(500)
        self.json({"status": "fuck you"})
        return

# @app.route("/actuator/gateway/routes")
# @app.route("/geoserver")
# @app.route("/boaform/admin/formLogin")
# @app.route("/portal/redlion")
# @app.route("/geoserver/web")
# @app.route("/cf_scripts/scripts/ajax/ckeditor/ckeditor.js")
# @app.route("/.env")
# @app.route("/manager/html")
# @app.route("/web_shell_cmd.gch")
##############################

class JSONHandler(tornado.web.RequestHandler):
    def prepare(self):
        if self.request.remote_ip in IP_BLACKLIST:
            self.status(403, "Forbidden")
            self.finish({"status": "whoops"})

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

    def json(self, data):
        self.write(json.dumps(data))


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
            self.set_status(400)
            return self.json({"status": "error", "message": "request must have a file"})
        file = self.request.files['file'][0]
        if file['filename'] == '':
            self.set_status(400)
            return self.json({"status": "error", "message": "request must have a file"})
        allowed_extensions = {".wav", ".mp3"}
        if not os.path.splitext(file['filename'])[1].lower() in allowed_extensions:
            self.set_status(400)
            return self.json({
                "status": "error",
                "message": f"file must be one of {', '.join(allowed_extensions)}"
            })

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
        text = self.request.get_argument('text')
        if text is None:
            self.set_status(400)
            return self.json({"status": "error", "message": "request must have text"})

        voice = self.request.get_argument("voice", "leo")
        k = int(self.request.get_argument("k", "1"))

        async with GPU:
            res = tts.text_to_wavs(text, voice, k)

        self.json({
            "status": "ok", "voice": voice, "text": text,
            "urls": [f"/static/{os.path.basename(r)}" for r in res]
        })


class BlogcastHandler(JSONHandler):
    async def post():
        url = self.request.get_argument('url')
        if url is None:
            self.set_status(400)
            return self.json({"status": "error", "message": "request must have a target URL"})

        voice = self.request.get_argument("voice", "leo")

        app.logger.debug(f"blogcast -- reading '{url}' as '{voice}'...")

        async with GPU:
            script = blogcast.script.script_from(url)

        res = []
        for el in tqdm.tqdm(script):
            async with GPU:
                res_tts = tts.text_to_wavs(text, voice, k)
            res.append({
                "text": el,
                "url": f"/static/{os.path.basename(res_tts[0])}"
            })

        self.json({
            "status": "ok", "voice": voice, "target": url,
            "result": res
        })

# @app.post("/v0/text/chat")
# class ChatHandler(JSONHandler):
#     def get():
#         return jsonify({"status": "ok", "stub": "TODO"})

# @app.post("/v0/text/generate")
# async def run_generate_text():
#     prompt = request.values.get('prompt')
#     if prompt is None:
#         return jsonify({"status": "error", "message": "request must have prompt"}), 400
#     max_new_tokens = request.values.get("max_new_tokens")

#     async with GPU:
#         return jsonify({"status": "ok", "result": basics.generate_text(prompt, max_new_tokens)})

# @app.post("/v0/image/describe")
# def run_describe():
#     url = request.values.get('url')
#     if url is None:
#         return jsonify({"status": "error", "message": "request must have url"}), 400
#     return jsonify({"status": "ok", "result": basics.caption_image(url)})


class StaticHandler(tornado.web.StaticFileHandler):
    def parse_url_path(self, url_path):
        if not url_path or url_path.endswith('/'):
            url_path = url_path + 'index.html'
        return url_path

ROUTES = [
    (r"/v0/health", HealthHandler)
    (r"/v0/audio/tts", TTSHandler),
    (r"/v0/audio/blogcast", BlogcastHandler),
    (r"/v0/audio/transcribe", TranscribeHandler),
    (r"/static/(.*)", StaticHandler, {"path": os.getcwd()})
    (r"(.*)", TrapCard)
]

async def main(port):
    app = tornado.web.Application(ROUTES)
    app.listen(port)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main(8181))
