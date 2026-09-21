"""Run-scoped opt-in control for the whole-order shared-knife strategy."""
from PySide6.QtWidgets import QCheckBox, QPushButton


def add_shared_knife_controls(owner):
    owner.shared_knife_button = QPushButton('多批次共用刀位生成PRN')
    owner.order_side_checkbox = QCheckBox('整单归侧双排（仅本次共刀任务）')
    owner.order_side_checkbox.setChecked(False)
    owner.order_side_checkbox.setToolTip(
        '主动勾选后，同一订单的全部件与双面只在固定刀位一侧；'
        '不符合的完整订单进入旋转文件夹。每次任务后自动关闭。')
    owner.shared_knife_button.clicked.connect(lambda: owner._download_selected(
        auto_print='shared_knife_order_side' if owner.order_side_checkbox.isChecked()
        else 'shared_knife'))
    owner.shared_knife_button.clicked.connect(
        lambda: owner.order_side_checkbox.setChecked(False))
    owner.shared_knife_button.setToolTip(
        '一次读取所选批次，优先使用当前固定刀位；同批次不同刀位的输出文件分别归入'
        '常规和旋转文件夹，按实际刀位分别生成PRN。不比较四种膜规格，也不启动物理打印。')
    visible = owner.platform_names == ('隆丰',)
    owner.shared_knife_button.setVisible(visible)
    owner.order_side_checkbox.setVisible(visible)
