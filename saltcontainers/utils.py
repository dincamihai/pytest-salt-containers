import time
import json
import logging
from functools import wraps

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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
                logger.debug('retry: ' + func.__name__)
                try:
                    output = func(*args, **kwargs)
                    success = (expected is None) or (output is expected)
                except Exception as exc:
                    logger.error(exc)
                    success = False
                    output = None
                if not success:
                    time.sleep(1)
            return output

        return wrapper
    return decorator


def load_json(data):
    try:
        return json.loads(data)
    except ValueError as err:
        raise ValueError(
            "{0}\nIncoming data: {1}".format(err, data))
    except TypeError as err:
        raise TypeError(
            "{0}\nIncoming data: {1}".format(err, data))
