"""Decode newline-delimited progress events from the cold-batch worker."""
import json
from pathlib import Path
from time import perf_counter


def consume_output(dialog):
    dialog._buffer += bytes(dialog.process.readAllStandardOutput()).decode(
        'utf-8', 'replace',
    )
    while '\n' in dialog._buffer:
        line, dialog._buffer = dialog._buffer.split('\n', 1)
        try:
            data = json.loads(line)
        except ValueError:
            if line.strip():
                dialog.log.appendPlainText(line)
            continue
        event = data.get('event')
        if event == 'timing':
            timing = dict(data['data'])
            timing['captured_at'] = perf_counter()
            dialog.layout_timings.emit(timing)
            continue
        if event == 'scan':
            message = f"正在扫描：{data['folder']}"
        elif event == 'batch_started':
            dialog._batch_started_at = perf_counter()
            dialog.timing_panel.reset()
            message = (f"第{data['index']}/{data['count']}批 · "
                       f"{Path(data['folder']).name} · {data['images']}张 · 开始")
        elif event == 'progress':
            message = (f"第{data['index']}/{data['count']}批 · "
                       f"{data['stage']} · {data['detail']}")
        elif event == 'batch_finished':
            dialog._batch_started_at = None
            message = (f"第{data['index']}批 {data['status']} · "
                       f"本批{data['wall_seconds']:.2f}秒 · "
                       f"累计{data['cumulative_seconds']:.2f}秒")
        elif event == 'finished':
            message = (f"{data['status']} · 成功{data['completed']}批 · "
                       f"失败{data['failed']}批 · 总计{data['total_seconds']:.2f}秒 · "
                       f"报告：{data['report']}")
        else:
            message = data.get('error', line)
        dialog.status.setText(message)
        dialog.log.appendPlainText(message)
        if event == 'batch_finished' and dialog.timing_panel.data:
            for row in dialog.timing_panel.data.get('steps', ()):
                dialog.log.appendPlainText(
                    f"  {row['name']}：{row['seconds']:.2f} 秒")
        dialog._refresh_elapsed()
