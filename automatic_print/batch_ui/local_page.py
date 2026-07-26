from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .pages import _table


def build_local_page(owner) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    intro = QLabel(
        "显示已经下载并解压到本机的生产批次。"
        "选择批次后会先显示全部图片名称，再进行排版。"
    )
    intro.setWordWrap(True)
    owner.local_summary = QLabel("尚未读取本地生产批次。")
    owner.local_table = _table(
        ["选择", "平台", "批次号", "图片数", "本地更新时间", "文件夹"],
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
    owner.local_test_mode.setChecked(True)
    owner.local_merge_batches = QCheckBox(
        "合并选中的批次为一个排版文件"
    )
    owner.filename_summary = QLabel("选择一个本地批次查看图片名称。")
    owner.filename_search = QLineEdit()
    owner.filename_search.setPlaceholderText("搜索文件名或尺码…")
    owner.filename_search.textChanged.connect(owner.filter_image_names)
    owner.copy_filenames_button = QPushButton("复制全部文件名")
    owner.copy_filenames_button.clicked.connect(owner.copy_image_names)
    filename_actions = QHBoxLayout()
    filename_actions.addWidget(owner.filename_search)
    filename_actions.addWidget(owner.copy_filenames_button)
    owner.filename_table = _table(
        ["序号", "图片文件名（包含尺码信息）", "相对位置"], 1
    )
    layout.addWidget(intro)
    layout.addWidget(owner.local_summary)
    layout.addWidget(owner.local_table)
    layout.addWidget(owner.local_test_mode)
    layout.addWidget(owner.local_merge_batches)
    layout.addLayout(actions)
    layout.addWidget(QLabel("批次图片名称"))
    layout.addWidget(owner.filename_summary)
    layout.addLayout(filename_actions)
    layout.addWidget(owner.filename_table)
    return page
