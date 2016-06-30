import os
import time
from docker import Client


TIME_LIMIT = 120


class TimeLimitReached(Exception):

    """Used in tests to limit blocking time."""


def time_limit_reached(start_time):
    if TIME_LIMIT < (time.time() - start_time):
        raise TimeLimitReached


def retry(func):
    success = False
    start_time = time.time()
    while not success and not time_limit_reached(start_time):
        print('retry: ' + func.func_name)
        success = func() is True
        if success is not True:
            time.sleep(1)
            continue
    return success
