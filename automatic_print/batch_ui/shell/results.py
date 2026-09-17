"""Present completed ERP actions without owning worker lifecycle."""
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from ...layout_engine.reporting.metrics import saving_text


def present_action_result(owner, result: dict) -> None:
    if result['type'] == 'batches_generated':
        owner.pending_batch_plan = None
        owner.generate_rules_button.setEnabled(False)
        text = (f"{result['platform']}：已成功生成 "
                f"{result['generated']} 个分类批次。")
        owner.batch_rule_summary.setText(text)
        QMessageBox.information(owner, '批次生成完成', text)
        return
    if result['type'] == 'downloaded':
        text = (f"{result['platform']}：已下载并解压 {len(result['files'])} 个文件。"
                '未启动排版；请回到本地排版页，点击开始排版。')
        owner.summary.setText(text)
        QMessageBox.information(owner, '下载完成', text)
        return
    mode = ('排版预览' if result.get('preview_only') else
            '测试小样' if result['test'] else '生产批次')
    merged_codes = result.get('merged_batches') or []
    merged_text = (f'已将 {len(merged_codes)} 个批次合并为一个排版文件。'
                   if merged_codes else '')
    savings = [item[1] for item in result['batches']]
    saving = saving_text({
        'saved_length_m': sum(item.get('saved_length_m', 0) for item in savings),
        'saved_percent': combined_percent(savings),
        'rotation_count': sum(item.get('rotation_count', 0) for item in savings),
    })
    if result['type'] == 'downloaded_and_processed':
        text = (f"{result['platform']}：已下载并解压 {len(result['files'])} 个文件，"
                f"已完成 {len(result['batches'])} 个{mode}。{merged_text}\n{saving}")
        if hasattr(owner, 'local_summary'):
            owner.refresh_local_batches()
    else:
        text = (f"{result['platform']}：已生成 {len(result['batches'])} 个{mode}排版图片。"
                f'{merged_text}\n{saving}')
    target = owner.local_summary if getattr(owner, 'local_only', False) else owner.summary
    target.setText(text)
    QMessageBox.information(owner, '处理完成', text)
    folder = Path(result['output_folder'])
    if folder.is_dir():
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))


def combined_percent(results: list[dict]) -> float:
    baseline = sum(item.get('baseline_height_mm', 0) for item in results)
    saved_mm = sum(item.get('saved_length_m', 0) * 1000 for item in results)
    return saved_mm / baseline * 100 if baseline else 0
