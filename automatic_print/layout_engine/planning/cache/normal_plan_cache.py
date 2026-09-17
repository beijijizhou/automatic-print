"""One normal baseline per film width, shared by concurrent comparisons."""
from concurrent.futures import Future
from dataclasses import replace
from threading import Lock


class NormalPlans:
    def __init__(self, compute):
        self.compute, self.entries, self.lock = compute, {}, Lock()

    def get(self, film, paths, config, report, prepared):
        with self.lock:
            leader = film not in self.entries
            future = self.entries.setdefault(film, Future())
        if leader:
            normal = replace(config, cutter_rotation_zone=False)
            effective = [normal]

            def capture(stage, current, total, filename):
                if stage == '批次刀位已确定':
                    effective[0] = replace(normal, cutter_knife_mm=current*25.4/total)
                report(stage, current, total, filename)

            try:
                result = self.compute(paths, normal, capture, prepared=prepared)
                future.set_result((result, effective[0], ''))
            except ValueError as exc:
                future.set_result((None, normal, str(exc)))
            except BaseException as exc:
                future.set_exception(exc)
                raise
        return future.result()
