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
