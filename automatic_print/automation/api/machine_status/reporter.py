"""Non-blocking, coalesced status publishing for production work."""

from queue import Empty, Full, Queue
from threading import Event, Thread
from time import monotonic

from .client import report_machine


class MachineStatusReporter:
    def __init__(self, send=report_machine, minimum_interval=2.0):
        self._send = send
        self._minimum_interval = float(minimum_interval)
        self._queue = Queue(maxsize=1)
        self._stopped = Event()
        self._thread = None
        self.last_error = ""

    def publish(self, **status):
        """Replace an obsolete pending heartbeat; production never waits on network."""
        if self._stopped.is_set():
            return
        try:
            self._queue.put_nowait(status)
        except Full:
            try:
                self._queue.get_nowait()
            except Empty:
                pass
            self._queue.put_nowait(status)
        if self._thread is None or not self._thread.is_alive():
            self._thread = Thread(
                target=self._run, name="machine-status-reporter", daemon=True
            )
            self._thread.start()

    def close(self):
        self._stopped.set()

    def _run(self):
        last_sent = 0.0
        while not self._stopped.is_set():
            try:
                status = self._queue.get(timeout=0.25)
            except Empty:
                if self._queue.empty():
                    return
                continue
            while True:
                delay = self._minimum_interval - (monotonic() - last_sent)
                if delay <= 0 or self._stopped.wait(min(delay, 0.25)):
                    break
            if self._stopped.is_set():
                return
            try:
                self._send(status)
                self.last_error = ""
            except Exception as error:
                self.last_error = str(error)
            last_sent = monotonic()
