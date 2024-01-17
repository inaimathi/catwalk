import asyncio
import json
import os

import tornado
import tqdm

import basics
import blogcast.script
import images
import model
import tts
import util

if not os.path.exists("static"):
    os.makedirs("static")

GPU = asyncio.Semaphore(1)

if os.path.exists("blacklist.txt"):
    with open("blacklist.txt", "r") as f:
        IP_BLACKLIST = set(f.read().splitlines())
else:
    IP_BLACKLIST = set([])


def _BAN(ip):
    print(f"BANNING {ip}...")
    with open("blacklist.txt", "a+") as bl:
        bl.write(f"{ip}\n")
    IP_BLACKLIST.add(ip)


class JSONHandler(tornado.web.RequestHandler):
    SUPPORTED_METHODS = tornado.web.RequestHandler.SUPPORTED_METHODS + ("CONNECT",)

    def prepare(self):
        if self.request.remote_ip in IP_BLACKLIST:
            return self.json({"status": "whoops"}, 403)

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

    def connect(self):
        _BAN(self.request.remote_ip)
        return self.json(
            {"status": "looks like you're going to the shadow realm, Jimbo"}, 400
        )

    def json(self, data, status=None):
        if status is not None:
            self.set_status(status)
        return self.write(json.dumps(data))


class TrapCard(JSONHandler):
    def prepare(self):
        if self.request.remote_ip in IP_BLACKLIST:
            return self.json({"status": "whoops"}, 403)
        _BAN(self.request.remote_ip)
        return self.json(
            {"status": "looks like you're going to the shadow realm, Jimbo"}, 400
        )


class HealthHandler(JSONHandler):
    def get(self):
        val = self.get_argument("value", None)
        res = {"status": "ok"}
        if val is not None:
            res["value"] = val
        return self.json(res)


class TranscribeHandler(JSONHandler):
    async def post(self):
        if "file" not in self.request.files:
            return self.json(
                {"status": "error", "message": "request must have a file"}, 400
            )
        file = self.request.files["file"][0]
        if file["filename"] == "":
            return self.json(
                {"status": "error", "message": "request must have a file"}, 400
            )
        allowed_extensions = {".wav", ".mp3"}
        if not os.path.splitext(file["filename"])[1].lower() in allowed_extensions:
            return self.json(
                {
                    "status": "error",
                    "message": f"file must be one of {', '.join(allowed_extensions)}",
                },
                400,
            )

        with open(
            util.fresh_file(
                "tmp-transcription-audio-", os.path.splitext(file.filename)
            ),
            "wb",
        ) as out:
            out.write(file["body"])

        async with GPU:
            return self.json({"status": "ok", "result": basics.transcribe(path)})


class ImageHandler(JSONHandler):
    async def post(self):
        prompt = self.get_argument("prompt")
        if prompt is None:
            return self.json(
                {"status": "error", "message": "request must have prompt"}, 400
            )

        negative_prompt = self.get_argument("negative_prompt", None)
        k = int(self.get_argument("k", "1"))
        width = int(self.get_argument("width", "1024"))
        height = int(self.get_argument("height", "1024"))
        steps = int(self.get_argument("steps", "50"))
        seed = self.get_argument("seed", None)
        if seed is not None:
            seed = int(seed)

        res = []
        for _ in range(k):
            async with GPU:
                path = images.generate_image(
                    prompt,
                    negative_prompt,
                    width=width,
                    height=height,
                    steps=steps,
                    seed=seed,
                )
                res.append(path)

        return self.json(
            {
                "status": "ok",
                "prompt": prompt,
                "urls": [f"/{os.path.basename(path)}" for path in res],
            }
        )


class TTSHandler(JSONHandler):
    def get(self):
        return self.json({"voices": tts.get_voices()})

    async def post(self):
        text = self.get_argument("text")
        if text is None:
            return self.json(
                {"status": "error", "message": "request must have text"}, 400
            )

        voice = self.get_argument("voice", "leo")
        k = int(self.get_argument("k", "1"))

        async with GPU:
            res = tts.text_to_wavs(text, voice, k)

        return self.json(
            {
                "status": "ok",
                "voice": voice,
                "text": text,
                "urls": [f"/{os.path.basename(r)}" for r in res],
            }
        )


class BlogcastHandler(JSONHandler):
    async def post(self):
        url = self.get_argument("url")
        if url is None:
            return self.json(
                {"status": "error", "message": "request must have a target URL"}, 400
            )

        voice = self.get_argument("voice", "leo")

        print(f"Generating cast of {url}...")
        async with GPU:
            script = blogcast.script.script_from(url)

        print(f"   create script of {len(script)} lines...")
        res = []
        for el in tqdm.tqdm(script, ascii=True):
            if isinstance(el, str):
                async with GPU:
                    res_tts = tts.text_to_wavs(el, voice, 1)
                res.append({"text": el, "url": f"/{os.path.basename(res_tts[0])}"})
            else:
                res.append(el)

        print("   done speaking...")
        response = {"status": "ok", "voice": voice, "target": url, "result": res}
        with open(util.fresh_file("blogcast-result-", ".json"), "w") as out:
            out.write(json.dumps(response))
        return self.json(response)


class ChatHandler(JSONHandler):
    def post(self):
        return self.json({"status": "ok", "stub": "TODO"})


class TextCompletionHandler(JSONHandler):
    async def post(self):
        prompt = self.get_argument("prompt")
        if prompt is None:
            return self.json(
                {"status": "error", "message": "request must have prompt"}, 400
            )

        max_new_tokens = self.get_argument("max_new_tokens")

        async with GPU:
            return self.json(
                {"status": "ok", "result": basics.generate_text(prompt, max_new_tokens)}
            )


class DescribeImageHandler(JSONHandler):
    async def post(self):
        url = self.get_argument("url")
        if url is None:
            return self.json(
                {"status": "error", "message": "request must have url"}, 400
            )

        async with GPU:
            return self.json({"status": "ok", "result": basics.caption_image(url)})


class UIHandler:
    def get(self):
        self.render("index.html")


class JobsHandler(JSONHandler):
    def options(self):
        return self.json({"TODO": "return info on differnet job types you can start"})

    def get(self):
        return self.json({"jobs": model.job_tree()})

    def post(self):
        job_type = self.get_argument("type")
        job_input = json.loads(self.get_argument("input"))
        parent = int(self.get_argument("parent"))
        return self.json(model.new_job(job_type, job_input, parent=parent))


class JobHandler(JSONHandler):
    def get(self, job_id):
        return self.json(model.job_by_id(int(job_id)))

    def post(self, job_id):
        return self.json({"TODO": "update a job"})


ROUTES = [
    (r"/", UIHandler),
    (r"/v0/health", HealthHandler),
    (r"/v0/audio/tts", TTSHandler),
    (r"/v0/audio/blogcast", BlogcastHandler),
    (r"/v0/audio/transcribe", TranscribeHandler),
    (r"/v0/text/chat", TranscribeHandler),
    (r"/v0/text/generate", TextCompletionHandler),
    (r"/v0/image/describe", DescribeImageHandler),
    (r"/v0/image/from_prompt", ImageHandler),
    (r"/v1/job", JobsHandler),
    (r"/v1/job/([0-9]+)", JobHandler),
]


async def main(port):
    print("Setting up app...")
    static_path = os.path.join(os.path.dirname(__file__), "static/")
    print(f"  static serving {static_path} ...")
    app = tornado.web.Application(
        ROUTES,
        debug=True,
        default_handler_class=TrapCard,
        static_path=static_path,
        static_url_prefix="/static/",
    )
    print(f"  listening on {port}...")
    app.listen(port)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main(8080))
