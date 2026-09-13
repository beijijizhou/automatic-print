from .decorations import combined_footprint
from .models import mm_to_px


def signed_mm(value, dpi):
    pixels = mm_to_px(abs(value), dpi)
    return -pixels if value < 0 else pixels


def rotated_qr(location, degrees):
    x, y = location.x_ratio, location.y_ratio
    if degrees == 90:
        return y, 1-x
    if degrees in {-90, 270}:
        return 1-y, x
    if degrees in {180, -180}:
        return 1-x, 1-y
    return x, y


def qr_label_layout(image_size, label_size, location, degrees, gap, offset_x, offset_y):
    width, height = image_size
    label_width, label_height = label_size
    x_ratio, y_ratio = rotated_qr(location, degrees)
    x = (-gap-label_width if x_ratio < 0.5 else width+gap) + offset_x
    y = min(max(0, round(y_ratio*height-label_height/2)), max(0, height-label_height)) + offset_y
    rx, ry, fw, fh = combined_footprint(image_size, [(x, y, label_width, label_height)])
    return rx, ry, x+rx, y+ry, fw, fh
