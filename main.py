import asyncio
import json
import os

import tornado

import audio
import basics
import model
import tts
import util
import worker

if not os.path.exists("static"):
    os.makedirs("static")

GPU = asyncio.Semaphore(1)


class PublicJSONHandler(tornado.web.RequestHandler):
    def prepare(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "*")
        self.set_header("Access-Control-Allow-Methods", "*")

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

    def json(self, data, status=None):
        if status is not None:
            self.set_status(status)
        return self.write(json.dumps(data))


class JSONHandler(tornado.web.RequestHandler):
    def prepare(self):
        auth_token = self.request.headers.get("X-Auth-Token", None)
        api_key = auth_token and model.api_key_by(key=auth_token)
        if not api_key:
            self.json(
                {"status": "looks like you're going to the shadow realm, Jimbo"}, 400
            )
            self.finish()
            return self.request.connection.close()

        self.api_key = api_key
        self.auth_token = auth_token

        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "*")
        self.set_header("Access-Control-Allow-Methods", "*")

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

    def json(self, data, status=None):
        if status is not None:
            self.set_status(status)
        return self.write(json.dumps(data))


class HealthHandler(PublicJSONHandler):
    def get(self):
        val = self.get_argument("value", None)
        res = {"status": "ok"}
        if val is not None:
            res["value"] = val
        return self.json(res)


class InfoHandler(PublicJSONHandler):
    def get(self):
        return self.json({"voices": tts.get_voices()})


class UIHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")


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

        path = util.fresh_file(
            "tmp-transcription-audio-", os.path.splitext(file.filename)
        )
        with open(path, "wb") as out:
            out.write(file["body"])

        async with GPU:
            return self.json({"status": "ok", "result": basics.transcribe(path)})


class DescribeImageHandler(JSONHandler):
    async def post(self):
        url = self.get_argument("url")
        if url is None:
            return self.json(
                {"status": "error", "message": "request must have url"}, 400
            )

        async with GPU:
            return self.json({"status": "ok", "result": basics.caption_image(url)})


class JobsHandler(JSONHandler):
    def options(self):
        return self.json(worker.AVAILABLE_JOBS)

    def get(self):
        return self.json({"jobs": model.jobs_by_api_key(self.api_key["id"])})

    def post(self):
        # TODO - check if the rate and credits of the current key
        job_type = self.get_argument("type")
        if job_type is None:
            return self.json(
                {"status": "error", "message": "request must have a `type`"}, 400
            )
        job_input = json.loads(self.get_argument("input"))
        if job_type is None:
            return self.json(
                {"status": "error", "message": "request must have an `input`"}, 400
            )
        parent = self.get_argument("parent_job", None)
        if parent is not None:
            parent = int(parent)
        res = model.new_job(job_type, job_input, parent=parent)
        worker.SocketServer.send_job_update(res)
        return self.json(res)


class JobHandler(JSONHandler):
    def get(self, job_id):
        job = model.job_by_id(int(job_id), include_children=True)
        if not job["api_key_id"] == self.api_key["id"]:
            return self.json({"status": "error", "message": "nope"}, 404)
        return self.json(job)

    def delete(self, job_id):
        should_delete = self.get_argument("shred", None)
        job = model.job_by_id(int(job_id))
        if not job["api_key_id"] == self.api_key["id"]:
            return self.json({"status": "error", "message": "nope"}, 404)
        res = model.update_job(
            job_id, status=("CANCELLED" if not should_delete else "DELETED")
        )
        if res is not None:
            worker.SocketServer.send_job_update(res)
            return self.json({"status": "ok"})
        return self.json({"status": "error"}, 400)

    def put(self, job_id):
        job = model.job_by_id(int(job_id))
        if not job["api_key_id"] == self.api_key["id"]:
            return self.json({"status": "error", "message": "nope"}, 404)
        res = model.update_job(job_id, status="STARTED", output={})
        if res is not None:
            worker.SocketServer.send_job_update(res)
            model.queue_job(job_id)
            return self.json({"status": "ok"})
        return self.json({"status": "error"}, 400)

    def post(self, job_id):
        status = self.get_argument("status", None)
        output = self.get_argument("output", None)
        if output is not None:
            output = json.loads(output)
        job = model.job_by_id(int(job_id))
        if not job["api_key_id"] == self.api_key["id"]:
            return self.json({"status": "error", "message": "nope"}, 404)
        res = model.update_job(int(job_id), output=output, status=status)

        if res is not None:
            worker.SocketServer.send_job_update(res)
            return self.json(res)
        return self.json({"status": "error", "message": "no change pushed"}, 400)


class AudioStitchHandler(JSONHandler):
    def post(self):
        files_and_silences = self.get_argument("stitch_list")
        if files_and_silences is None:
            return self.json(
                {"status": "error", "message": "request must have `stitch_list`"}, 400
            )
        files_and_silences = json.loads(files_and_silences)
        files_and_silences = (
            os.path.join("static", os.path.basename(f)) if type(f) is str else f
            for f in files_and_silences
        )
        res_file = audio.stitch(files_and_silences)
        return self.json({"file": util.force_static(res_file)})


ROUTES = [
    (r"/", UIHandler),
    (r"/favicon.ico", tornado.web.RedirectHandler, dict(url=r"/static/favicon.ico")),
    (r"/v0/health", HealthHandler),
    (r"/v0/audio/transcribe", TranscribeHandler),
    (r"/v0/image/describe", DescribeImageHandler),
    (r"/v1/info", InfoHandler),
    (r"/v1/job", JobsHandler),
    (r"/v1/job/([0-9]+)", JobHandler),
    (r"/v1/job/updates", worker.SocketServer),
    (r"/v1/audiofile/stitch", AudioStitchHandler),
]


async def main(port):
    print("Setting up app...")
    static_path = os.path.join(os.path.dirname(__file__), "static/")
    print("  initializing model...")
    model.init()
    model.refill_queue()
    print("  starting worker thread...")
    worker.make_worker().start()
    print(f"  static serving {static_path} ...")
    app = tornado.web.Application(
        ROUTES,
        debug=True,
        static_path=static_path,
        static_url_prefix="/static/",
    )
    print(f"  listening on {port}...")
    app.listen(port)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main(8080))
