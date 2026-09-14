"""Bounded rolling scheduling shared by analysis and production queues."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from ..cancellation import TaskCancelled


def run_queue(folders, calculate, workers, cancellation=None, failed=None):
    records, errors, pending = [], [], {}
    next_index, stopped = 0, False
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='batch-queue') as pool:
        while pending or next_index < len(folders):
            try:
                if cancellation:
                    cancellation.check()
            except TaskCancelled:
                stopped = True
            while not stopped and len(pending) < workers and next_index < len(folders):
                pending[pool.submit(calculate, next_index, folders[next_index])] = next_index
                next_index += 1
            if not pending:
                break
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                index = pending.pop(future)
                try:
                    records.append((index, future.result()))
                except TaskCancelled:
                    stopped = True
                except Exception as error:
                    errors.append({'folder': str(folders[index]), 'error': str(error)})
                    if failed:
                        failed(index, folders[index], str(error))
    return {'records': [record for _, record in sorted(records)], 'errors': errors,
            'stopped': stopped, 'actual_parallelism': min(workers, next_index)}
