"""Own the lifetime of one immutable source-data snapshot per batch task."""
from functools import wraps

from .measurement_session import measurement_session


def batch_measurements(function):
    @wraps(function)
    def call(*args, **kwargs):
        with measurement_session():
            return function(*args, **kwargs)
    return call
