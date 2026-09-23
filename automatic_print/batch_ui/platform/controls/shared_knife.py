"""Run-scoped opt-in control for the whole-order shared-knife strategy."""
from PySide6.QtWidgets import QPushButton


def add_shared_knife_controls(owner):
    owner.shared_knife_button = QPushButton('多批次共用刀位生成PRN')
    owner.shared_knife_button.clicked.connect(lambda: _start_shared_knife(owner))
    owner.shared_knife_button.setToolTip(
        '一次读取所选批次，优先使用当前固定刀位；同批次不同刀位的输出文件分别归入'
        '常规和旋转文件夹，按实际刀位分别生成PRN。不比较四种膜规格，也不启动物理打印。'
        '需要整单归侧时，请在主界面“测试与诊断”中勾选“整单归侧双排”。')
    visible = owner.platform_names == ('隆丰',)
    owner.shared_knife_button.setVisible(visible)


def _start_shared_knife(owner):
    checkbox = _main_order_side_checkbox(owner)
    owner._download_selected(auto_print=(
        'shared_knife_order_side' if checkbox is not None and checkbox.isChecked()
        else 'shared_knife'
    ))
    if checkbox is not None:
        checkbox.setChecked(False)


def _main_order_side_checkbox(owner):
    host = getattr(owner, 'settings_host', None)
    home = getattr(getattr(host, 'automation_home', None), 'label_quick_panel', None)
    return getattr(home, 'order_side_checkbox', None)
