"""Run-scoped opt-in control for the whole-order shared-knife strategy."""
from PySide6.QtWidgets import QPushButton
from ...ui.copyable_text import copyable_checkbox


def add_shared_knife_controls(owner):
    owner.shared_knife_button = QPushButton('多批次共用刀位生成PRN')
    tooltip = ('主动勾选后，同一订单的全部件与双面只在固定刀位一侧；'
               '不符合的完整订单进入旋转文件夹。每次任务后自动关闭。')
    (owner.order_side_control, owner.order_side_checkbox,
     owner.order_side_label) = copyable_checkbox(
        '整单归侧双排（仅本次共刀任务）', tooltip, owner
    )
    owner.order_side_checkbox.setChecked(False)
    host = getattr(owner, 'settings_host', None)
    home = getattr(getattr(host, 'automation_home', None), 'label_quick_panel', None)
    main_checkbox = getattr(home, 'order_side_checkbox', None)
    if main_checkbox is not None:
        owner.order_side_checkbox.setChecked(main_checkbox.isChecked())
        main_checkbox.toggled.connect(owner.order_side_checkbox.setChecked)
        owner.order_side_checkbox.toggled.connect(main_checkbox.setChecked)
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
    owner.order_side_control.setVisible(visible)
