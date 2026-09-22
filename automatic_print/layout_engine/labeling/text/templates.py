"""Canonical production label templates independent of platform badge geometry."""


def numbered_template(settings):
    template = settings.label_text_template
    if settings.label_source_order_enabled:
        template = source_order_template(template)
    if (settings.label_source_order_enabled and settings.cutter_mode != 'free'
            and not any(token in template for token in ('{尺码}', '{size}'))):
        template = (template.strip() + ' · 尺码 {尺码}').strip(' ·')
    if settings.platform_reuse_qr and settings.platform_name:
        if not any(token in template for token in ('{平台}', '{platform}')):
            if '{尺码}' in template:
                template = template.replace('{尺码}', '{平台} · {尺码}', 1)
            elif '{size}' in template:
                template = template.replace('{size}', '{platform} · {size}', 1)
            else:
                template = (template.strip() + ' · {平台} · {尺码}').strip(' ·')
        if not any(token in template for token in ('{尺码}', '{size}')):
            template = (template.strip() + ' · {尺码}').strip(' ·')
    if settings.label_machine_enabled and not any(
            token in template for token in ('{机器号}', '{machine}')):
        template = (template.strip() + ' {机器号}').strip()
    if settings.label_sequence_enabled and not any(
            token in template for token in ('{编号}', '{number}')):
        template = (template.strip() + ' {编号}').strip()
    return template


def source_order_template(template):
    if not any(token in template for token in ('{批次}', '{文件夹}', '{batch}')):
        template = (template.strip() + ' {批次}').strip()
    return (template.strip() + ' · 正序 {编号}/{总数} · 倒序 {倒序}/{总数}').strip()
