import datetime
import hashlib
import json
import queue
import uuid
from queue import Queue

from pytrivialsql import sqlite

DB = sqlite.Sqlite3("catwalk.db")

__JOB_QUEUE = Queue()


def add_job(job_id):
    __JOB_QUEUE.put(job_id)


def add_jobs(job_ids):
    for jid in job_ids:
        add_job(jid)


JOB_STATUS = [
    "STARTED",
    "RUNNING",
    "WAITING_FOR_CHILDREN",
    "CANCELLED",
    "COMPLETE",
    "ERRORED",
    "DELETED",
]


def init():
    DB.create(
        "api_keys",
        [
            "id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL",
            "key TEXT NOT NULL UNIQUE",
            "rate_limit INTEGER",
            "credits TEXT",
            "created DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL",
            "updated DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL",
        ],
    )
    DB.create(
        "jobs",
        [
            "id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL",
            "api_key_id INTEGER",
            "parent_job INTEGER",
            "job_type TEXT",
            "input TEXT",
            "output TEXT",
            "status TEXT NOT NULL DEFAULT 'STARTED'",
            "created DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL",
            "updated DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL",
            "FOREIGN KEY(api_key_id) REFERENCES api_keys(id)",
        ],
    )
    DB.create(
        "casts",
        [
            "id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL",
            "api_key_id INTEGER",
            "job_id INTEGER",
            "url TEXT",
            "flag INTEGER",
            "title TEXT",
            "audio TEXT",
            "script TEXT",
            "state TEXT",
            "created DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL",
            "updated DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL",
            "FOREIGN KEY(api_key_id) REFERENCES api_keys(id)",
            "FOREIGN KEY(job_id) REFERENCES jobs(id)",
        ],
    )


def hashed_key(raw_key):
    return hashlib.sha512(raw_key.encode("utf-8")).hexdigest()


def api_key_by(id=None, key=None):
    assert (id is not None) or (key is not None), "Needs either `id` or `key`"
    where_map = {}
    if id is not None:
        where_map["id"] = id
    if key is not None:
        where_map["key"] = key
    try:
        return DB.select("api_keys", "*", where=where_map)[0]
    except IndexError:
        return None


def fresh_key(rate_limit, initial_credits=0, key=None):
    if key is None:
        key = str(uuid.uuid4())
    key_id = DB.insert(
        "api_keys", key=hashed_key(key), credits=initial_credits, rate_limit=rate_limit
    )
    return key, api_key_by(id=key_id)


def _transform_job(raw_job):
    raw_job["input"] = json.loads(raw_job["input"])
    if outp := raw_job["output"]:
        raw_job["output"] = json.loads(outp)
    # for dttype in ["created", "updated"]:
    #     if type(val := raw_job[dttype]) is str:
    #         raw_job[dttype] = datetime.datetime.fromisoformat(val)
    return raw_job


def all_jobs():
    return DB.select(
        "jobs", "*", where=("NOT", {"status": "DELETED"}), transform=_transform_job
    )


def jobs_by_api_key(api_key_id):
    return DB.select(
        "jobs",
        "*",
        where=("NOT", {"status": "DELETED", "api_key_id": api_key_id}),
        transform=_transform_job,
    )


def jobs_by_id(ids):
    return DB.select("jobs", "*", where={"id": set(ids)}, transform=_transform_job)


def job_by_id(job_id, include_children=False):
    job = DB.select("jobs", "*", where={"id": job_id}, transform=_transform_job)[0]
    if include_children:
        job["children"] = jobs_by_parent(job_id)
    return job


def all_children_finished_p(job_id):
    children_status = DB.select("jobs", ["status"], where={"parent_job": job_id})
    if {c["status"] for c in children_status} - {
        "COMPLETE",
        "ERRORED",
        "CANCELLED",
        "DELETED",
    }:
        return False
    return True


def jobs_by_parent(job_id):
    return DB.select(
        "jobs", "*", where={"parent_job": job_id}, transform=_transform_job
    )


def refill_queue():
    """Meant to be run on startup. It re-populates the job queue with
    jobs still on disk, but not yet comlpeted"""
    queuable = DB.select(
        "jobs",
        "*",
        where=(
            "NOT",
            {"status": {"COMPLETE", "CANCELLED", "WAITING_FOR_CHILDREN", "DELETED"}},
        ),
        transform=_transform_job,
    )
    for job in queuable:
        if job["status"] == "ERRORED":
            update_job(job["id"], status="STARTED")
        add_job(job["id"])


def new_job(job_type, job_input, parent=None):
    now = datetime.datetime.now()
    props = {
        "job_type": job_type,
        "input": json.dumps(job_input),
        "created": now,
        "updated": now,
    }
    if parent is not None:
        assert job_by_id(parent), f"No such job: {parent}"
        props["parent_job"] = parent
    job_id = DB.insert("jobs", **props)
    job = job_by_id(job_id)
    add_job(job["id"])
    return job


def update_job(job_id, input=None, output=None, status=None):
    update = {}
    if input is not None:
        update["input"] = json.dumps(input)
    if output is not None:
        update["output"] = json.dumps(output)
    if status is not None:
        assert status in JOB_STATUS
        update["status"] = status
    if update:
        update["updated"] = datetime.datetime.now()
        DB.update("jobs", update, where={"id": job_id})
        return job_by_id(job_id)
    return None


def queue_job(job_id):
    assert job_by_id(job_id), f"No such job: {job_id}"
    add_job(job_id)


def pull_job():
    jid = __JOB_QUEUE.get()
    job = job_by_id(jid)
    if not job["status"] in {"CANCELLED", "DELETED"}:
        return job
    return pull_job()


def get_job():
    try:
        jid = __JOB_QUEUE.get_nowait()
        job = job_by_id(jid)
        if not job["status"] in {"CANCELLED", "DELETED"}:
            return job
        return get_job()
    except queue.Empty:
        return None


def job_to_cast(job):
    # FIXME - create the initial cast from a job
    #         (possibly also output metadata for already completed jobs?)
    pass


def _transform_cast(raw_cast):
    raw_cast["flag"] = bool(raw_cast["flag"])
    raw_cast["script"] = json.loads(raw_cast["script"])
    raw_cast["state"] = json.loads(raw_cast["state"])
    return raw_cast


def cast_by(cast_id=None, job_id=None):
    assert cast_id or job_id, "Need either cast_id or job_id"
    where = {}
    if cast_id is not None:
        where["id"] = cast_id
    if job_id is not None:
        where["job_id"] = job_id
    return DB.select("casts", "*", where=where, transform=_transform_cast)[0]


def _db_proc_process_jobs_to_casts():
    cast_jobs = DB.select("jobs", "*", where={"job_type": "blogcast"})
    for job in cast_jobs:
        print(f"Converting job {job['id']} ...")
        job_to_cast(job)
