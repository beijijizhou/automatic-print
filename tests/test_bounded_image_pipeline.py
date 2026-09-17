from threading import Lock
from automatic_print.layout_engine.intake.preparation.image_pipeline import prepared_images


def test_preparation_buffers_are_bounded_and_closed_on_stop():
    state = {'alive': 0, 'peak': 0}
    lock = Lock()
    class Image:
        closed = False
        def __init__(self):
            with lock:
                state['alive'] += 1
                state['peak'] = max(state['peak'], state['alive'])
        def close(self):
            with lock:
                if not self.closed:
                    self.closed = True
                    state['alive'] -= 1
    stream = prepared_images(lambda item: (Image(), item), list(range(200)), 2)
    next(stream)
    stream.close()
    assert state['alive'] == 0
    assert state['peak'] <= 2
