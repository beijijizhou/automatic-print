"""Build the checked-in, de-identified Haloo preview fixture.

The card position and transparent header follow a local Haloo production
sample. No customer artwork, order identifiers, or decodable QR pixels are
copied into the repository.
"""
from pathlib import Path

from PIL import Image, ImageDraw


DESTINATION = Path(__file__).resolve().parents[1] / "assets" / "haloo-preview-sample.png"


def build() -> None:
    image = Image.new("RGBA", (800, 680))
    draw = ImageDraw.Draw(image)
    # Haloo's right-hand paper card leaves a transparent header to its left.
    draw.rectangle((540, 0, 799, 170), fill="white")
    draw.rectangle((548, 9, 675, 30), fill="#188659")
    draw.text((552, 12), "HALOO DEMO", fill="white")
    draw.text((552, 42), "SIZE M", fill="#202020")
    draw.text((552, 61), "PREVIEW ONLY", fill="#202020")
    # Finder-like squares establish the printed-card geometry, not a real QR.
    for x, y in ((698, 12), (753, 12), (698, 69)):
        draw.rectangle((x, y, x + 38, y + 38), fill="#523219")
        draw.rectangle((x + 6, y + 6, x + 32, y + 32), fill="white")
        draw.rectangle((x + 12, y + 12, x + 26, y + 26), fill="#523219")
    for x, y in ((746, 68), (778, 79), (744, 111), (703, 121), (777, 135)):
        draw.rectangle((x, y, x + 12, y + 12), fill="#523219")
    draw.rectangle((540, 171, 799, 190), fill="#743b85")
    # Generic garment silhouette replaces the original customer artwork.
    draw.polygon(
        ((235, 276), (326, 238), (366, 285), (434, 285), (474, 238),
         (565, 276), (630, 365), (565, 405), (530, 378), (530, 652),
         (270, 652), (270, 378), (235, 405), (170, 365)),
        fill="#f2f5f7", outline="#8ea2ad",
    )
    draw.arc((353, 228, 447, 316), 0, 180, fill="#8ea2ad", width=4)
    # Preview-only scale: a generous physical header survives large label settings.
    image.save(DESTINATION, dpi=(25.4, 25.4), optimize=True)
    image.close()


if __name__ == "__main__":
    build()
