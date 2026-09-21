"""Present completed ERP actions without owning worker lifecycle."""
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from ...layout_engine.reporting.metrics import saving_text


def present_action_result(owner, result: dict) -> None:
    if result['type'] == 'route_batches_generated':
        owner.pending_route_plan = None
        owner.route_generate_button.setEnabled(False)
        codes = '、'.join(result['codes'])
        text = (
            f"{result['platform']} / {result['route']}："
            f"已生成 {result['items']} 项，批次号 {codes}。"
            "\n批次管理状态：\n" + "\n".join(result['status'])
        )
        owner.route_summary.setText(text)
        owner.log.appendPlainText(text)
        QMessageBox.information(owner, '批次生成完成', text)
        return
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
        open_folder = getattr(owner, 'open_download_folder', None)
        folder = Path(result['output_folder'])
        if (
            open_folder is not None
            and open_folder.isChecked()
            and folder.is_dir()
        ):
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(folder.resolve()))
            )
        return
    if result['type'] == 'downloaded_processed_and_printed':
        printed = result.get('print_files') or []
        errors = result.get('print_errors') or []
        layout_errors = result.get('layout_errors') or []
        routes = result.get('batch_routes') or {}
        skipped = result.get('skipped_print_batches') or []
        writing = sum(not item.get('riin_complete', True) for item in printed)
        finished = len(printed) - writing
        text = (
            f"{result['platform']}：已下载并完成 {len(result['batches'])} 个批次排版；"
            f"已加入PrintExp {len(printed)} 个PRN（RIIN已完成 {finished}，仍在写入 {writing}）。"
        )
        if writing:
            text += '\n仍在写入的PRN须等RIIN完成，并核对PrintExp预览后再实际打印。'
        if errors:
            text += "\nPRN失败：" + "；".join(
                f"{item['batch']}：{item['error']}" for item in errors
            )
        if routes:
            fixed_files = sum(sum(part['unattended'] for part in route.get('parts', ()))
                              if route.get('parts') else int(route['unattended'])
                              for route in routes.values())
            changed_files = sum(sum(not part['unattended'] for part in route.get('parts', ()))
                                if route.get('parts') else int(not route['unattended'])
                                for route in routes.values())
            attended = [name for name, route in routes.items()
                        if any(not part['unattended'] for part in route.get('parts', ()))
                        or not route['unattended']]
            text += (f'\n共用刀位 {result["shared_knife_mm"]:g} 毫米：'
                     f'常规（固定刀位）{fixed_files} 个文件，旋转（其他刀位）{changed_files} 个文件。'
                     '\n仅生成并加载PRN，尚未启动物理打印。')
            if attended:
                text += '\n旋转区需换刀：' + '；'.join(
                    f'{name}：{routes[name]["reason"]}' for name in attended)
        if layout_errors:
            text += '\n排版失败：' + '；'.join(
                f'{item["batch"]}：{item["error"]}' for item in layout_errors)
        if skipped:
            text += "\n按用户停止请求未启动：" + "、".join(skipped)
        owner.summary.setText(text)
        owner.log.appendPlainText(text)
        QMessageBox.information(owner, '自动化排版完成', text)
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
