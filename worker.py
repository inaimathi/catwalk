import json
import threading

import tornado
import tornado.websocket

import model
import tts
import util
from blogcast import script

AVAILABLE_JOBS = {
    "blogcast": {"inputs": ["url", "voice", "k", "threshold", "max_tries"]},
    "tts": {"inputs": ["text", "voice", "k", "threshold", "max_tries"]},
}  # "image", "caption", "code_summarize"


class SocketServer(tornado.websocket.WebSocketHandler):
    CLIENTS = set()
    IOloop = tornado.ioloop.IOLoop.current()

    def __init__(self, *args):
        super().__init__(*args)
        SocketServer.IOloop = tornado.ioloop.IOLoop.current()

    def open(self):
        SocketServer.CLIENTS.add(self)

    def close(self):
        SocketServer.CLIENTS.remove(self)

    @classmethod
    def send_message(cls, message):
        msg = json.dumps(message)
        print(f"UPDATING {len(cls.CLIENTS)} WS CLIENTS...")
        for client in cls.CLIENTS:
            client.write_message(msg)

    @classmethod
    def send_job_update(cls, job):
        if job is None:
            return
        cls.IOloop.asyncio_loop.call_soon_threadsafe(
            cls.send_message,
            {
                "job_id": job["id"],
                "status": job["status"],
                "parent": job["parent_job"],
                "output": job["output"],
            },
        )


def update_parents(job):
    pid = job["parent_job"]
    while pid is not None:
        if model.all_children_finished_p(pid):
            model.update_job(pid, status="COMPLETE")
            parent = model.job_by_id(pid)
            pid = parent["parent_job"]
        return


def work_on(job):
    jtype = job["job_type"]
    assert jtype in set(AVAILABLE_JOBS.keys())
    jid = job["id"]
    SocketServer.send_job_update(model.update_job(jid, status="RUNNING"))

    try:
        if jtype == "tts":
            inp = job["input"]
            text = inp.pop("text")
            res = tts.text_to_wavs(text, **inp)
            paths = [util.force_static(r) for r in res]
            SocketServer.send_job_update(
                model.update_job(
                    jid,
                    status="COMPLETE",
                    output=paths,
                )
            )
        elif jtype == "blogcast":
            scr = script.script_from(job["input"]["url"])
            SocketServer.send_job_update(
                model.update_job(
                    jid,
                    status="WAITING_FOR_CHILDREN",
                    output={"script": scr, "raw_script": scr},
                )
            )
            inp = {k: v for k, v in job["input"].items() if not k == "url"}
            for ln in scr:
                if type(ln) is str:
                    SocketServer.send_job_update(
                        model.new_job(
                            "tts",
                            {"text": ln, **inp},
                            parent=jid,
                        )
                    )
        update_parents(job)
    except Exception as e:
        SocketServer.send_job_update(
            model.update_job(jid, status="ERRORED", output={"error": str(e)})
        )


def _worker():
    while True:
        work_on(model.pull_job())


def make_worker():
    return threading.Thread(target=_worker, daemon=True)
