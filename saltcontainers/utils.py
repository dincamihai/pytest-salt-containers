import time
from functools import wraps


TIME_LIMIT = 120


class TimeLimitReached(Exception):

    """Used in tests to limit blocking time."""


def time_limit_reached(start_time):
    if TIME_LIMIT < (time.time() - start_time):
        raise TimeLimitReached


def retry(func, *args, **kwargs):
    @wraps(func)
    def wrapper(*args, **kwargs):
        success = False
        start_time = time.time()
        while not success and not time_limit_reached(start_time):
            print('retry: ' + func.func_name)
            success = func(*args, **kwargs) is True
            if not success:
                time.sleep(1)
        return success

    return wrapper
