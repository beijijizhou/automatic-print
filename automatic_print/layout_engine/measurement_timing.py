"""Exclusive per-thread substep costs; parallel costs are not wall-clock totals."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from threading import RLock
from time import perf_counter

STACK = ContextVar('measurement_timing_stack', default=())


class MeasurementTiming:
    def __init__(self):
        self.lock, self.rows = RLock(), {}

    def add(self, name, seconds):
        with self.lock:
            row = self.rows.setdefault(name, {'name': name, 'seconds': 0.0, 'calls': 0})
            row['seconds'] += seconds
            row['calls'] += 1

    def snapshot(self):
        with self.lock:
            return {'steps': [dict(row) for row in self.rows.values()],
                    'basis': '线程累计独占耗时；已扣除嵌套子步骤，并行耗时不能与总耗时相加'}


@contextmanager
def substep(name):
    from .measurement_session import SESSION
    session = SESSION.get()
    if session is None:
        yield
        return
    parent = STACK.get()
    frame = [perf_counter(), 0.0]
    token = STACK.set(parent+(frame,))
    try:
        yield
    finally:
        elapsed = perf_counter()-frame[0]
        STACK.reset(token)
        if parent:
            parent[-1][1] += elapsed
        session.timing.add(name, max(0.0, elapsed-frame[1]))


def measured(name):
    def decorate(function):
        @wraps(function)
        def call(*args, **kwargs):
            with substep(name):
                return function(*args, **kwargs)
        return call
    return decorate


def decode_source(source):
    # Pillow otherwise charges full PNG decoding to the first crop operation.
    if getattr(source, 'tile', None):
        with substep('源图片像素读取与解压'):
            source.load()
    return source


def measurement_text(data):
    if not data:
        return ''
    lines = ['测量子步骤（线程累计，不是墙钟总耗时）']
    if data.get('cache_hit'):
        lines.append('本次命中排版缓存，以下测量未执行，耗时为0。')
    for row in data['steps']:
        lines.append(f"{row['name']}：{row['seconds']:.3f} 秒 · {row['calls']} 次")
    lines.append(data['basis'])
    return '\n'.join(lines)
