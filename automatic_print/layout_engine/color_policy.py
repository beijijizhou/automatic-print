"""Colors group whole orders; mixed-color orders must never be split."""
from .source_metadata import source_color, color_key


def order_color(order):
    colors = {source_color(path) for path in order}
    return next(iter(colors)) if len(colors)==1 and '未识别颜色' not in colors else None


def order_color_key(order):
    color = order_color(order)
    return color_key(color) if color else (-1,'')


def validate_color_order(planned):
    from .order_groups import complete_orders
    orders = complete_orders([path for path,_ in sorted(planned,key=lambda e:(e[1].row_y_px,e[1].x_px))])
    colors = [color for order in orders if (color:=order_color(order)) is not None]
    if colors != sorted(colors,key=color_key):
        raise ValueError('订单颜色未聚集或被旋转分区打散，禁止输出。')
