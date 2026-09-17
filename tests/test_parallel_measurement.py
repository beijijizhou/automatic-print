from dataclasses import replace
from threading import Barrier, get_ident, enumerate as threads
import pytest
from automatic_print.layout_engine.intake.preparation.item_factory import read_items
from automatic_print.layout_engine.measurement.parallel_measurement import read_parallel
from test_parallel_film_geometry import qr_sources, settings


def test_parallel_measurement_matches_serial_geometry_and_labels(tmp_path):
    paths = qr_sources(tmp_path)
    config = replace(settings(), allow_rotation=True)
    serial = read_items(paths, replace(config, worker_threads=1), None)
    parallel = read_items(paths, replace(config, worker_threads=4), None)
    assert serial == parallel
    assert not any(t.name.startswith('image-measure') for t in threads())


def test_measurement_runs_four_workers_with_bounded_queue_and_original_numbers(tmp_path):
    paths = qr_sources(tmp_path)
    barrier, observed = Barrier(4), set()
    def measure(paths, config, progress):
        if get_ident() not in observed:
            observed.add(get_ident())
            barrier.wait(5)
        number = dict(config.sequence_numbers)[str(paths[0].resolve())]
        return [[number]], {number: paths[0].name}
    items, labels = read_parallel(measure, paths, replace(settings(), worker_threads=4), None)
    assert len(observed) == 4 and items == [[i] for i in range(1, 13)]
    assert len(labels) == 12


def test_measurement_honors_eight_worker_setting(tmp_path):
    paths=qr_sources(tmp_path)
    barrier,observed=Barrier(8),set()
    def measure(paths,config,progress):
        if get_ident() not in observed:
            observed.add(get_ident())
            barrier.wait(5)
        return [[paths[0].name]],{}
    items,_=read_parallel(measure,paths,replace(settings(),worker_threads=8),None)
    assert len(observed)==8 and len(items)==len(paths)


def test_measurement_stop_does_not_enqueue_whole_batch(tmp_path):
    paths = qr_sources(tmp_path)
    visited = []
    def measure(paths, config, progress):
        visited.append(paths[0])
        return [[1]], {}
    def stop(stage, current, total, filename):
        if current:
            raise RuntimeError('stop')
    with pytest.raises(RuntimeError, match='stop'):
        read_parallel(measure, paths, replace(settings(), worker_threads=4), stop)
    assert len(visited) <= 4
    assert not any(t.name.startswith('image-measure') for t in threads())
