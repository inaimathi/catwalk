import datetime
import json
import queue
from queue import Queue

from pytrivialsql import sqlite

DB = sqlite.Sqlite3("catwalk.db")

__JOB_QUEUE = Queue()


def init():
    DB.create(
        "jobs",
        [
            "id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL",
            "parent_job INTEGER",
            "job_type TEXT",
            "input TEXT",
            "output TEXT",
            "status TEXT",
            "created DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL",
            "updated DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL",
        ],
    )


def _transform_job(raw_job):
    raw_job["input"] = json.loads(raw_job["input"])
    if outp := raw_job["output"]:
        raw_job["output"] = json.loads(outp)
    for dttype in ["created", "updated"]:
        if type(val := raw_job[dttype]) is str:
            raw_job[dttype] = datetime.datetime.fromisoformat(val)
    return raw_job


def all_jobs():
    return DB.select("jobs", "*", transform=_transform_job)


def job_tree():
    node_map = {}
    res = []
    job_list = all_jobs()
    for job in job_list:
        job["children"] = []
        if job["parent_job"] is None:
            res.append(job)
        else:
            try:
                node_map[job["parent_job"]]["children"].append(job)
            except KeyError:
                pass
        node_map[job["id"]] = job
    return res


def job_by_id(job_id):
    return DB.select("jobs", "*", where={"id": job_id}, transform=_transform_job)[0]


def all_children_finished_p(job_id):
    children_status = DB.select("jobs", ["status"], where={"parent_job": job_id})
    if {c["status"] for c in children_status} - {"COMPLETE", "ERRORED"}:
        return False
    return True


def jobs_by_parent(job_id):
    return DB.select(
        "jobs", "*", where={"parent_job": job_id}, transform=_transform_job
    )


def new_job(job_type, job_input, parent=None):
    now = datetime.datetime.now()
    props = {
        "job_type": job_type,
        "input": json.dumps(job_input),
        "created": now,
        "updated": now,
    }
    if parent is not None:
        props["parent_job"] = parent
    job_id = DB.insert("jobs", **props)
    job = job_by_id(job_id)
    __JOB_QUEUE.put(job)
    return job


def update_job(job_id, output=None, status=None):
    update = {}
    if output is not None:
        update["output"] = json.dumps(output)
    if status is not None:
        update["status"] = status
    if update:
        update["updated"] = datetime.datetime.now()
        DB.update("jobs", update, where={"id": job_id})
        return job_by_id(job_id)
    return None


# STATUS = ["STARTED", "RUNNING", "WAITING_FOR_CHILDREN", "COMPLETE", "ERRORED"]


def pull_job():
    return __JOB_QUEUE.get()


def get_job():
    try:
        return __JOB_QUEUE.get_nowait()
    except queue.Empty:
        return None
