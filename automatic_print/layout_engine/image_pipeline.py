"""Bounded image preparation: do not enqueue an entire large batch."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor


def prepared_images(prepare, items, workers):
    pending, source = deque(), iter(items)
    pool = ThreadPoolExecutor(max_workers=workers)
    def submit_next():
        item = next(source, None)
        if item is not None:
            pending.append(pool.submit(prepare, item))
    try:
        for _ in range(workers):
            submit_next()
        while pending:
            value = pending.popleft().result()
            try:
                yield value
            finally:
                value[0].close()
            submit_next()
    finally:
        for future in pending:
            future.cancel()
        pool.shutdown(wait=True, cancel_futures=True)
        for future in pending:
            if not future.cancelled() and future.exception() is None:
                future.result()[0].close()
