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
powershell -ExecutionPolicy Bypass -Command "irm 'https://raw.githubusercontent.com/beijijizhou/automatic-print/main/windows/bootstrap-test-computer.ps1?v=0.1.412' | iex"
```

该入口用于指定测试电脑拉取已经通过本次相关检查并推送到 `main` 的源码。正式生产电脑使用 GitHub
Release 安装包；源码更新、Release 和生产验收是三个独立状态。

亿点万象源码模式从工厂共享盘 `\\192.168.11.28\dtf\.automatic-print\ydwx-gateway.key`
读取受限网关密钥，首次成功后保存在当前 Windows 用户配置目录。各部门电脑无需登录亿点万象；
共享盘临时断开时已有缓存的电脑仍可访问在线平台，新电脑首次使用仍须能读取共享盘。
平台断网时无法读取或下载新批次。需要使用其他共享位置时可设置
`AUTOMATIC_PRINT_YDWX_SHARE_KEY_FILE` 为该文件路径。

DTF 部门顶部的“DTF 平台账号”可查看服务端账号配置，并对支持服务端登录的平台按需验证。
赛博已退出合作，不在清单中；S2B 使用独立网关。账号已配置不代表登录有效或生产批次下载已接入。
管理员更新 after-sales 的私有凭据后，可在自己的电脑重新执行
`python scripts/sync_dtf_platform_credentials.py --after-sales-root /path/to/after-sales`
同步九个平台配置；测试电脑不需要这份私有文件。

亿点万象下载会按批次名中的明确 UV 材质 SKU 选择 250×130 cm 画布容量，保留原 ZIP，
再按 ZIP 实际图片数生成 `完整稿件-分组/1-48` 等文件夹。`1-48` 表示第 1 组有 48 张；
1040 的容量为每组 72 张。新增稿件单独进入 `新增稿件-分组`，不当作完整批次。

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

未经用户针对本次任务明确同意，不运行或通过 CI 触发完整测试。合并到 `main` 本身不构成授权。
本地推送前运行本次调用链的针对性测试；如用户明确要求完整测试，再运行：

```bash
.venv/bin/python -m pytest -q
```

已运行的针对性测试失败时禁止推送。准备正式 Windows Release 时，还需要更新版本、
取得所需验证授权、创建对应标签，并由 Windows 工作流构建安装包。GitHub `main` 分支应要求
`Quality Gate` 的针对性检查通过；不得把该检查称为完整测试或生产验收。

## 本地真实批次验收

专用自托管测试 Runner 已停用。完整验收改由人工在本机运行自动测试套件，并按
`docs/BATCH_REGRESSION.md` 的矩阵核验不同平台的真实输出；不自动接单或启动物理打印。

## 输出

默认在输入批次同级的 `切膜机文件` 保存已核验 PNG；切膜输出按实际刀位分别放入 `常规` 和
`旋转` 子文件夹，报告保存在平级的 `排版日志`。输出保留源图物理尺寸和透明通道；具体刀位、旋转、间距、膜规格和安全规则以
`docs/BUSINESS_RULES.md` 为准。
