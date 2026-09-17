# Automatic Print

Windows 本地生产排版工具：读取批次图片，按订单、双面、尺码、膜宽和切膜安全约束生成可导入
RIIN 或其他 RIP 软件的 PNG。

## 项目文档

- [当前业务与生产规则](docs/BUSINESS_RULES.md)
- [工程、架构、测试与发布规则](docs/PROJECT_RULES.md)
- [当前活动模块归属](docs/CURRENT_STATE.md)
- [共享能力与复用入口](docs/FUNCTION_CATALOG.md)

文档只描述当前状态。规则和实现历史通过 Git 提交记录查看。

## 测试电脑安装或更新

在 PowerShell 运行：

```powershell
powershell -ExecutionPolicy Bypass -Command "irm 'https://raw.githubusercontent.com/beijijizhou/automatic-print/main/windows/bootstrap-test-computer.ps1?v=0.1.283' | iex"
```

该入口用于指定测试电脑拉取已经通过完整测试并推送到 `main` 的源码。正式生产电脑使用 GitHub
Release 安装包；源码更新、Release 和生产验收是三个独立状态。

## 本地开发

支持 Python 3.11/3.12；正式桌面环境为 Windows 10/11，macOS 可用于开发测试。

```bash
python -m venv .venv
pip install -r requirements.txt
python -m automatic_print
```

开发时可使用自动重载入口：

```bash
python dev.py
```

## 验证与发布

针对性测试用于开发反馈：

```bash
.venv/bin/python -m pytest -q tests/相关测试.py
```

任何源码推送前必须运行完整门禁：

```bash
.venv/bin/python -m pytest -q
```

只要存在失败就禁止推送。准备正式 Windows Release 时，还需要更新版本、完整测试、创建对应标签，
并由 Windows 工作流构建安装包。GitHub `main` 分支应要求 `Quality Gate` 通过，避免未经完整测试的
代码进入测试电脑更新来源。

## 输出

默认在输入批次同级的 `切膜机文件` 下创建以批次命名的任务目录，保存 PNG、`排版报告.txt`
和 `manifest.json`。输出保留源图物理尺寸和透明通道；具体刀位、旋转、间距、膜规格和安全规则以
`docs/BUSINESS_RULES.md` 为准。
