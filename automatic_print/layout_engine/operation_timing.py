"""Exclusive wall-clock phase timings, including folder discovery."""
from threading import RLock
from time import perf_counter

PROGRESS_PHASES = {
    '扫描文件夹': '扫描文件名', '分析批次': '订单与尺码分析',
    '读取图片尺寸': '读取尺寸与标签', '识别膜标签': '读取尺寸与标签',
    '计算批次刀位': '刀位与排版计算', '批次刀位已确定': '刀位与排版计算',
    '计算排版': '刀位与排版计算',
    '比较旋转区域': '旋转区域比较', '切膜安全检查': '刀位与排版计算',
    '比较末尾旋转': '末尾大尺码旋转比较',
}


class OperationTiming:
    def __init__(self, clock=perf_counter):
        self.clock, self.lock = clock, RLock()
        self.started = self.changed = clock()
        self.current, self.status, self.durations = '', '运行中', {}

    def phase(self, name):
        with self.lock:
            if name == self.current or self.status != '运行中':
                return False
            now = self.clock()
            if self.current:
                self.durations[self.current] += now - self.changed
            self.current, self.changed = name, now
            self.durations.setdefault(name, 0.0)
            return True

    def finish(self, status='已完成'):
        with self.lock:
            if self.status == '运行中':
                now = self.clock()
                if self.current:
                    self.durations[self.current] += now - self.changed
                self.changed, self.status = now, status
            elif status != '已完成':
                self.status = status
            return self.snapshot()

    def snapshot(self):
        with self.lock:
            now = self.clock() if self.status == '运行中' else self.changed
            entries = [{'name': name, 'seconds': seconds + (
                now-self.changed if name == self.current and self.status == '运行中' else 0),
                'running': name == self.current and self.status == '运行中'}
                for name, seconds in self.durations.items()]
            return {'steps': entries, 'total_seconds': now-self.started,
                    'status': self.status, 'captured_at': now, 'active_phase': self.current}


def timing_report(data):
    total = data['total_seconds']
    lines = [f"{data['status']} · 总计 {total:.2f} 秒"]
    lines.extend(f"{step['name']}：{step['seconds']:.2f} 秒（{step['seconds']/max(total, .001):.1%}）"
                 for step in data['steps'])
    if data['steps']:
        slowest = max(data['steps'], key=lambda step: step['seconds'])
        lines.append(f"最耗时步骤：{slowest['name']}")
    lines.append('计时从文件名扫描开始，到批次信息整理完成；不含耗时报告及批次记录的写入、界面等待和后台缩略图。')
    lines.append('大图引擎延迟计算，解码与合成工作可能计入像素安全检查或保存；各阶段耗时不代表纯磁盘或纯 CPU 时间。')
    return '\n'.join(lines)
