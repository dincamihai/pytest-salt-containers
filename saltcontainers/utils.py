import time
from functools import wraps


TIME_LIMIT = 120


def time_limit_reached(start_time):
    if TIME_LIMIT < (time.time() - start_time):
        return True


def retry(expected=None):
    def decorator(func, *args, **kwargs):
        @wraps(func)
        def wrapper(*args, **kwargs):
            success = False
            output = None
            start_time = time.time()
            while not success and not time_limit_reached(start_time):
                print('retry: ' + func.func_name)
                try:
                    output = func(*args, **kwargs)
                    success = (expected is None) or (output is expected)
                except Exception as exc:
                    print exc.message
                    success = False
                    output = None
                if not success:
                    time.sleep(1)
            return output

        return wrapper
    return decorator
