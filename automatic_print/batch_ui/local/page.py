from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..platform.pages import table_widget
from ...ui.workbench.overview import LabelQuickPanel


def build_local_page(owner) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    intro = QLabel(
        "选择本机图片文件夹，点击开始排版；使用已保存参数，合成过程直接显示在主界面。"
    )
    intro.setWordWrap(True)
    owner.start_layout_button = QPushButton('选择文件夹并开始排版…')
    owner.start_layout_button.clicked.connect(lambda: owner.window().choose_and_generate())
    owner.manual_layout_button = owner.start_layout_button  # Compatibility: one primary action.
    owner.local_summary = QLabel("尚未读取本地生产批次。")
    owner.local_table = table_widget(
        ["选择", "来源", "批次号", "图片数", "本地更新时间", "文件夹"],
        5,
    )
    owner.local_table.currentCellChanged.connect(
        owner.local_batch_changed
    )
    owner.local_refresh_button = QPushButton("刷新本地文件")
    owner.local_refresh_button.clicked.connect(owner.refresh_local_batches)
    owner.local_select_button = QPushButton("全选本地批次")
    owner.local_select_button.clicked.connect(owner.select_all_local)
    owner.local_process_button = QPushButton("排版选中的本地批次")
    owner.local_process_button.clicked.connect(
        owner.process_selected_local_batches
    )
    owner.local_open_button = QPushButton("打开本地文件夹")
    owner.local_open_button.clicked.connect(owner.open_local_folder)
    actions = QHBoxLayout()
    for button in (
        owner.local_refresh_button,
        owner.local_select_button,
        owner.local_process_button,
        owner.local_open_button,
    ):
        actions.addWidget(button)
    owner.local_test_mode = QCheckBox(
        "快速测试：普通模式首批 5 张；合并模式每批 5 张"
    )
    owner.local_test_mode.setChecked(owner.preferences.value("local/test_mode", True, bool))
    owner.local_merge_batches = QCheckBox(
        "合并选中的批次为一个排版文件"
    )
    owner.local_merge_batches.setChecked(owner.preferences.value("local/merge_batches", False, bool))
    owner.filename_summary = QLabel("选择一个本地批次查看图片名称。")
    owner.filename_search = QLineEdit()
    owner.filename_search.setPlaceholderText("搜索文件名或尺码…")
    owner.filename_search.textChanged.connect(owner.filter_image_names)
    owner.copy_filenames_button = QPushButton("复制全部文件名")
    owner.copy_filenames_button.clicked.connect(owner.copy_image_names)
    filename_actions = QHBoxLayout()
    filename_actions.addWidget(owner.filename_search)
    filename_actions.addWidget(owner.copy_filenames_button)
    owner.filename_table = table_widget(
        ["序号", "图片文件名（包含尺码信息）", "相对位置"], 1
    )
    layout.addWidget(QLabel("本地图片排版"))
    layout.addWidget(intro)
    window = owner.window()
    if hasattr(window, "label_settings"):
        owner.label_quick_panel = LabelQuickPanel(
            window.label_settings, window.color_block_settings, page, window=window
        )
        from ...ui.batch_input_panel import build_batch_input, build_batch_tools
        owner.batch_input_panel = build_batch_input(owner, owner.label_quick_panel)
        layout.addWidget(owner.batch_input_panel)
        owner.batch_tools = build_batch_tools(owner.label_quick_panel)
        layout.addWidget(owner.label_quick_panel)
        window.run_log.hide()
        owner.log.hide()
    # Keep legacy workflow objects available to workers, but out of the workbench.
    for widget in (
        owner.platform, owner.output, owner.local_summary, owner.local_table,
        owner.local_test_mode, owner.local_merge_batches, owner.filename_summary,
        owner.filename_search, owner.copy_filenames_button, owner.filename_table,
        owner.local_refresh_button, owner.local_select_button,
        owner.local_process_button, owner.local_open_button,
    ):
        widget.setParent(page)
        widget.hide()
    return page
