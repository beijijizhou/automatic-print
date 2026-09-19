from automatic_print.layout_engine import LayoutSettings
from automatic_print.layout_engine.labeling.text.templates import numbered_template


def settings(**values):
    return LayoutSettings(**(
        dict(label_sequence_enabled=True, label_text_template='CY') | values
    ))


def test_numbered_template_adds_only_enabled_automatic_fields():
    assert numbered_template(settings(label_text_template='{编号} CY')) == '{编号} CY'
    assert numbered_template(settings(label_sequence_enabled=False)) == 'CY'
    assert numbered_template(settings(label_machine_enabled=True)) == 'CY {机器号} {编号}'
    assert numbered_template(settings(
        label_machine_enabled=True,
        label_text_template='CY {机器号} {编号}',
    )) == 'CY {机器号} {编号}'


def test_cutting_header_label_includes_order_size_once():
    cutting = settings(cutter_mode='dual', preserve_header_gap=True,
                       label_source_order_enabled=True, label_machine_enabled=True)
    result = numbered_template(cutting)
    assert result.count('{尺码}') == 1
    assert '{批次}' in result and '{机器号}' in result
    assert numbered_template(settings(cutter_mode='dual', label_source_order_enabled=True,
        label_text_template='订单 {尺码}')).count('{尺码}') == 1
