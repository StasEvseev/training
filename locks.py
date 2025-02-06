from contextlib import contextmanager

import redis

redis_client = redis.Redis(host="localhost", port=6379, db=0)

LOCK_KEY = "lock:process_all_workouts"
LOCK_TIMEOUT = 600


@contextmanager
def acquire_lock(lock_name, timeout):
    lock = redis_client.lock(lock_name, timeout=timeout)
    have_lock = lock.acquire(blocking=False)
    try:
        yield have_lock
    finally:
        if have_lock:
            lock.release()


@contextmanager
def acquire_lock_process_all_workouts():
    with acquire_lock(LOCK_KEY, LOCK_TIMEOUT) as have_lock:
        if not have_lock:
            return
        yield have_lock
