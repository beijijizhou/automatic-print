"""Recorded developer-machine benchmark, not a prediction for Windows machines."""

REFERENCE = {
    'date': '2026-09-14', 'version': '0.1.158', 'batch': '609142039033',
    'images': 58, 'changed_images': 32, 'unchanged_images': 26,
    'host': 'Mac ARM · 8GB内存 · 本地磁盘',
    'cache': '间距副本已有缓存；当前版本几何缓存未命中',
    'vertical_spacing_mm': 8, 'membrane_gap_mm': 40,
    'generation_seconds': 12.93267116700008,
    'source_copy_check_seconds': 5.5026259159931215,
    'saved_corridor_check_seconds': 23.863868458996876,
    'save_seconds': 8.87, 'width_px': 4110, 'height_px': 150448, 'dpi': 179.9844,
}


def reference_text():
    data = REFERENCE
    if 'generation_seconds' not in data:
        return '独立基准测试尚未完成，不显示未经验证的耗时。'
    return (f"真实生产图片独立基准 · {data['date']} · 测试源码{data['version']}\n"
            f"完整生成：{data['generation_seconds']:.3f}秒 · 其中PNG保存：{data['save_seconds']:.3f}秒（已包含，不再相加）\n"
            f"独立间距副本原像素复核：{data['source_copy_check_seconds']:.3f}秒 · "
            f"独立保存后整批刀位复核：{data['saved_corridor_check_seconds']:.3f}秒（均在生成之外）\n\n"
            f"批次{data['batch']} · {data['images']}张\n"
            f"环境：{data['host']}\n缓存：{data['cache']}\n"
            f"参数：60厘米膜，可用580毫米；跟随原图{data['dpi']:.4f}DPI；"
            f"上下间距8毫米；膜标签内部最小间距40毫米；双列，允许整批/尾部旋转\n"
            f"画布：{data['width_px']} × {data['height_px']}像素\n\n"
            f"{data['changed_images']}张补足后的副本：全部原有RGBA像素逐块相等；"
            f"{data['unchanged_images']}张间距已足够，直接保留原文件。\n"
            '刀位复核覆盖保存PNG的全部常规/旋转区域完整高度，不以两个样本推断整批。\n'
            '以上两项独立复核在生成计时之外运行，不是每次生产新增的等待步骤。'
            '副本比对不是声称输出PNG全部图案与原图逐像素全等。\n\n'
            '历史首次补足40毫米：20.111秒，使用旧5毫米排间距；当时独立复核未单独计时，'
            '不能与本次缓存已存在的8毫米结果当作同条件提速对照。\n'
            '这是开发电脑单次参考数据，不代表测试电脑耗时，也不代表切膜机实物验收。'
            '打开本页只展示已有记录，不扫描图片或运行基准。')
