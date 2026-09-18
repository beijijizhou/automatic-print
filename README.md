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
powershell -ExecutionPolicy Bypass -Command "irm 'https://raw.githubusercontent.com/beijijizhou/automatic-print/main/windows/bootstrap-test-computer.ps1?v=0.1.287' | iex"
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

### RIIN独立管理员控制入口

RIIN要求管理员权限时，在已登录的Windows桌面运行以下命令，并手动确认UAC弹窗：

```powershell
.venv\Scripts\python.exe -m automatic_print.automation.api.riin inspect --elevate --report riin-inspect.json
```

该入口只提升一次指定操作。支持`inspect`、`open-import`、`import`、`confirm-import`和`import-menu`；
`import`需要`--source`图片目录，递归读取PNG，使用`--chunk-index`指定从0开始的导入分段。
必须在RIIN文件选择框已打开时提交；提交后先核对“导入图像设置”，确认参数再执行`confirm-import`。
报告中的`submitted_count`只表示提交文件数，不能代替RIIN加载完成后的数量核验。当前不启动物理打印，
也尚未提供一键目录导入并排版流程。

文件输出使用`open-output`、`begin-file-output`、`save-print-file --output 文件.prn`，
只允许“文件”发送方式，且拒绝覆盖现有PRN。`inspect-printexp`检查PrintExp窗口，
`load-printexp --output 文件.prn`提交已有文件；报告`load_requested`仅表示提交，
需要核对PrintExp预览或任务列表确认加载成功。以上命令均需要`--report`，可加`--elevate`。
使用`select-document --document 文档标题`明确选择输出文档。已在本机完成单图PRN生成和PrintExp预览加载验证；跨子目录批量导入仍需逐批核验，尚未接入主界面一键流程。
`new-document`创建空白RIIN文档，适用于新批次输出，避免与已有测试图片混合。

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

## Windows 自托管测试机

专用 Windows 测试机使用 `codex/windows-test` 分支和 `Windows test machine` 工作流，执行完整
自动测试、真实批次排版验收、Windows 安装包构建，并上传测试报告、耗时、闪退日志和 EXE。
Runner 仅绑定本仓库，标签为 `automatic-print`；工作流不接受 `pull_request` 触发，避免在持久化
生产测试电脑上运行不可信分支代码。

在仓库的 `Settings > Actions > Runners > New self-hosted runner` 生成一小时有效的注册令牌后，
以管理员 PowerShell 运行：

```powershell
.\windows\setup-actions-runner.ps1
```

脚本会以隐藏输入方式读取一次性令牌，避免令牌进入 PowerShell 命令历史。

测试机默认使用 `C:\actions-runner\real-batches\smoke\YD-CY-YD001` 中的稳定生产样本。
如需替换或扩充样本，可在 Actions 仓库变量 `AUTOMATIC_PRINT_REAL_BATCH_PATHS` 中保存真实批次
绝对路径，多个目录用分号分隔。也可以手动触发工作流时临时指定批次目录和要测试的提交 SHA。
真实图片回归会在单元测试失败时继续执行，确保报告同时包含代码测试和生产数据兼容性结果。
`windows/real-batch-suite.json` 另行固定至少十个独立批次文件夹的验收矩阵：三个由固定种子选出的
Haloo 批次、各两个隆丰、莆田和 S2B 完整批次，以及隆丰 `609172109020` 的 200 PNG 冷/热缓存性能门禁。先运行
`windows/stage-real-batch-suite.ps1`，把 NAS 源图只读复制到 `C:\actions-runner\real-batches\acceptance`；
Runner 服务不直接依赖映射盘。每批使用独立进程、缓存状态和输出目录，单批失败后仍继续其余批次，
最终统一判定；报告核对源文件未变化、补距像素、保存后刀道和订单完整性。200 PNG 使用8段并行输出，
冷、热缓存生成时间都必须不超过30秒。生成图仅保留在测试机，不上传生产队列，也不触发物理打印。

## 输出

默认在输入批次同级的 `切膜机文件` 下创建以批次命名的任务目录，保存 PNG、`排版报告.txt`
和 `manifest.json`。输出保留源图物理尺寸和透明通道；具体刀位、旋转、间距、膜规格和安全规则以
`docs/BUSINESS_RULES.md` 为准。
