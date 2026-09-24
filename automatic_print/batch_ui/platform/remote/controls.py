"""Remote production-task controls shared by platform workbenches."""

from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton

from .broadcast import BroadcastBatchDispatcher
from .dispatch import RemoteBatchDispatcher


def build_remote_controls(owner):
    owner.remote_dispatch_button = QPushButton("发送到指定机器生成 PRN")
    owner.remote_dispatch_button.clicked.connect(owner.dispatch_selected_to_machine)
    owner.remote_dispatch_button.setToolTip(
        "把当前勾选批次和当前排版参数发送给指定在线机器；目标机负责下载、"
        "排版、生成PRN并加载PrintExp，不会启动物理打印。"
    )
    owner.remote_broadcast_button = QPushButton("发送到所有可应答机器（测试）")
    owner.remote_broadcast_button.clicked.connect(
        lambda: dispatch_selected_to_all(owner)
    )
    owner.remote_broadcast_button.setToolTip(
        "逐台实时检测M1–M11，最终确认后向全部正确应答的"
        "机器分别发送同一批次；不会启动物理打印。"
    )
    owner.remote_dispatch_status = QLabel(
        "可将当前勾选批次发送到指定机器或全部实时应答的机器。"
    )
    owner.remote_dispatch_status.setWordWrap(True)
    owner.remote_batch_dispatcher = RemoteBatchDispatcher(owner)
    owner.remote_broadcast_dispatcher = BroadcastBatchDispatcher(owner)


def dispatch_selected_to_all(owner):
    selected = owner._selected_batch_numbers()
    if not selected:
        QMessageBox.warning(owner, "请选择批次", "请至少选择一个可下载批次。")
        return
    owner.remote_broadcast_dispatcher.start(
        owner.platform.currentData(), selected, owner._current_layout_settings()
    )
