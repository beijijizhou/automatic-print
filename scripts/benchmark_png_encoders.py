"""Small reproducible encoder-only benchmark; never modifies production input."""
from io import BytesIO
from statistics import median
from time import perf_counter
import imagecodecs
import numpy as np
from PIL import Image
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automatic_print.layout_engine.rendering.png.fast import encode_pixels, chunk
from automatic_print.layout_engine.rendering.storage.atomic_png import save_png
from automatic_print.layout_engine.domain.models import LayoutSettings
from tempfile import TemporaryDirectory
import struct


def main():
    rng = np.random.default_rng(42)
    pixels = np.zeros((10000, 2000, 4), dtype=np.uint8)
    for y in range(0, 10000, 1000):
        pixels[y:y+750, 120:920, :3] = rng.integers(0, 256, (750, 800, 3), dtype=np.uint8)
        pixels[y:y+750, 120:920, 3] = 255
        pixels[y:y+750, 1100:1900] = pixels[y:y+750, 120:920]
    image = Image.fromarray(pixels)
    def pillow():
        stream = BytesIO()
        image.save(stream, format='PNG', compress_level=1)
        return stream.getvalue()
    encoders = {
        'Pillow-1': pillow,
        'libpng-RLE-SUB': lambda: imagecodecs.png_encode(pixels, level=1, strategy=3, filter=16),
        'libspng-1': lambda: imagecodecs.spng_encode(pixels, level=1),
        'libspng-UP-1': lambda: imagecodecs.spng_encode(pixels, level=1, filter=32),
        'libpng-UP-1': lambda: imagecodecs.png_encode(pixels, level=1, filter=32),
    }
    def native():
        data = encode_pixels(pixels, 1)
        stream = BytesIO()
        stream.write(b'\x89PNG\r\n\x1a\n')
        for kind, body in ((b'IHDR', struct.pack('>IIBBBBB', 2000, 10000, 8, 6, 0, 0, 0)),
                           (b'IDAT', data), (b'IEND', b'')):
            for piece in chunk(kind, body):
                stream.write(piece)
        return stream.getvalue()
    encoders['native-UP-libdeflate'] = native
    for name, encoder in encoders.items():
        seconds = []
        for _ in range(3):
            start = perf_counter()
            encoded = encoder()
            seconds.append(perf_counter()-start)
        decoded = np.asarray(Image.open(BytesIO(encoded)))
        assert np.array_equal(decoded, pixels)
        print(f'{name}: {median(seconds):.3f}s; {len(encoded)/1e6:.2f}MB; pixels verified')
    with TemporaryDirectory(prefix='png-save-benchmark-') as directory:
        for fast in (False, True):
            seconds = []
            for trial in range(3):
                canvas = image.copy()
                target = Path(directory)/f'{fast}-{trial}.png'
                settings = LayoutSettings(png_fast_encoding=fast, save_memory_unlimited=True)
                start = perf_counter()
                save_png(canvas, target, settings, False, None)
                seconds.append(perf_counter()-start)
                with Image.open(target) as output:
                    assert np.array_equal(np.asarray(output), pixels)
            print(f'file-save fast={fast}: {median(seconds):.3f}s; full RGBA verified')


if __name__ == '__main__':
    main()
