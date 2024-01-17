import threading

import model
import tts
from blogcast import script


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
    assert jtype in {"blogcast", "tts"}  # "image", "caption", "code_summarize"
    jid = job["id"]
    model.update_job(jid, status="RUNNING")
    try:
        if jtype == "tts":
            inp = job["input"]
            text = inp.pop("text")
            res = tts.text_to_wavs(text, **inp)
            model.update_job(jid, status="COMPLETE", output=res)
        elif jtype == "blogcast":
            scr = script.script_from(job["input"]["url"])
            model.update_job(jid, status="WAITING_FOR_CHILDREN", output={"script": scr})
            inp = {k: v for k, v in job["input"].items() if not k == "url"}
            for ln in scr:
                if type(ln) is str:
                    model.new_job(
                        "tts",
                        {"text": ln, **inp},
                        parent=jid,
                    )
        update_parents(job)
    except Exception as e:
        model.update_job(jid, status="ERRORED", output={"error": str(e)})


def _worker():
    while True:
        work_on(model.get_job())


def make_worker():
    return threading.Thread(_worker, daemon=True)
