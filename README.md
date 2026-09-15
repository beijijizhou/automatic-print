# Automatic Print

Windows desktop application for combining a folder of images into print-ready layout canvases that can be imported directly into RIIN or another RIP application.

## 测试电脑一键安装或更新

在测试电脑上打开 PowerShell，复制并运行：

```powershell
powershell -ExecutionPolicy Bypass -Command "irm 'https://raw.githubusercontent.com/beijijizhou/automatic-print/main/windows/bootstrap-test-computer.ps1?v=0.1.188' | iex"
```

同一条命令既可首次安装，也可在以后下载最新代码并更新运行环境。

界面版本显示为“日期 · 当日第几次更新”，例如 `版本 2026-09-13 · 第45次更新`，不再同时堆叠数字版本和发版日期。次数按发布迭代计数，不是打开软件或点击检查更新的次数；同日递增、换日从第01次开始。内部数字版本保留用于更新比较，可在版本文字上悬停查看。

四方案比较默认开启，显式预览或开始排版后，数据区的四行表格及排版报告会显示 60/45 厘米膜各自不旋转与允许旋转的长度、耗膜面积及图片占位率；面积最省的方案标绿。比较使用自动刀位，扣除当前 RIIN 预留，不自动换膜，也不保存四份比较大图；可在打印参数“膜规格比较”主动关闭以减少计算。跨膜宽以“物理膜宽 × 长度”的平方米比较，图片占位率包含生产图片本身的透明区域，不是油墨覆盖率；长度为分段前结果。升级首次将旧默认关闭状态迁移为开启，此后手动修改仍保存。

需要清除残留参数时，先停止任务，再到打印参数底部点击“恢复默认设置并退出”。确认后清除排版参数、标签文字、机器号、手动旋转和上次文件路径，软件退出；重新打开恢复默认值。不删除原图片、输出文件或平台登录信息。重置不保证解决尚未定位的性能问题。

从源码版 0.1.67（2026-09-13）起，主界面的“检查更新”可直接检查主分支代码，确认后自动拉取代码、同步依赖并安全重启，不再要求下载安装包。旧版电脑需先用上面的命令更新一次，之后直接点击按钮即可。排版、保存或后台预览运行时不会执行更新；本地代码有修改时停止更新，不会覆盖。

本地工作台点击“开始排版”直接使用当前已保存参数生成文件，不打开参数确认窗口。主界面显示整批真实排版和逐张处理进度：待处理图片淡化，已处理图片为绿色边框；保存大图时保留整批预览。该缩略图展示引擎处理进度，不是大图磁盘写入的像素回读。

主界面保留常用标签、排版操作、耗时、预览和总结。订单/尺码分析、手动旋转、切割明细、仅预览及处理日志集中在“批次详情与检查”独立窗口；打印参数仍从底部单独打开，不占主界面。

标签文字手动输入，新配置不预填示例文字；已有文字继续保留。当前机器号与每批 1 至最后一张的序号自动显示，无需“添加机器号”，已有变量不重复附加；分段沿用整批编号。生产平台下拉框默认“隆丰”，可填写其他实际平台名称；蜂鸟/Haloo 是 ERP，不作为平台选项。平台名称作为独立醒目标记，放在二维码最近一侧的图片外，整段高度按真实二维码适配；普通标签保持原字号。预览和输出共用位置，旋转后重新适配，不覆盖图案、不跨刀位；识别失败禁止输出，可在标签设置中关闭平台标记。平台、机器号和序号选择自动保存，不触发 ERP 访问。

主界面及打印参数使用统一操作图标：蓝色按钮代表开始排版/生成，红色按钮代表停止，普通操作使用次级样式；保留中文文字、键盘焦点和明确的禁用状态。

默认输出统一收纳在图片文件夹同级的“切膜机文件”中，再按批次创建独立任务文件夹；例如读取 `D:\订单\批次123`，输出到 `D:\订单\切膜机文件\批次123_JOB_时间\批次123_标签名.png`。完整长图、分段 PNG、切割说明与耗时报告放在同一任务目录。打印参数可指定其他保存位置，其中也会建立“切膜机文件”；文件夹名和标签名仍保留，重名不覆盖旧图。旧输出不自动搬移。
它会自动准备 Git、Python 3.12、Google Chrome、Playwright 及项目所需依赖，
然后创建带有 HA 图标的“Haloo Automatic”桌面入口并启动程序。
以后可以直接双击桌面入口打开。

默认开启“上线快速模式”：选择文件夹不先计算预览，点击开始排版后统一扫描、显示文件名、读取尺寸、排版与保存。不进行全批旋转搜索。单件批次默认只比较末尾 3XL 及以上完整尺码块的几种旋转后缀，计入区域间距、红线和留白后仍省膜才采用；每行一张，不拆双面，同尺码不拆区。混合多件或归属不明的批次不自动走此快速末尾旋转。完整旋转区搜索仍需主动开启。

打印参数可设置 RIIN 已配置的左右预留（默认各 10 毫米）：600 毫米膜按 580 毫米可用宽度排版，450 毫米膜按 430 毫米排版。只扣除容量，不在输出图中重复添加边距；请与 RIIN 实际配置保持一致。

单件订单按尺码从小到大连续排版，包含单件双面；小图不跨尺码配对。同尺码单件也不能拆到不同旋转区域，输出前会按实际位置检查，违规禁止保存。

单排图片的色块和标签固定在输出文件最左边缘，不允许独占右分区。右侧色块仅用于真正并排的右图；手动左分区放不下时提示调整刀位或使用单列，不能绕过安全检查。

上下垂直间距默认 5 毫米；固定切膜模式的水平距离由整批刀位、左右分区及色块位置计算，不叠加这 5 毫米。已保存的自定义间距继续保留，可在打印参数中修改。自由排版不使用刀位，界面会单独说明其间距同时用于水平与垂直方向。

主界面增加“分步耗时”：从扫描文件名开始记录各大步骤的秒数、占比及最耗时步骤，支持复制；输出目录保存 `耗时报告.txt`，批次记录保存详细计时。大图延迟计算可能计入安全检查或保存，不能将保存阶段当作纯磁盘耗时。报告/批次记录自身写入和独立缩略图不计入该总时间。

刀位搜索复用订单与尺码分析，配对使用数值几何而非重复构造排版对象，并合并左右可放置状态等价的候选刀位；保留原搜索目标和整批真实像素安全检查。

打印参数支持可选分段输出：默认 1 个完整文件，可设置多个连续 PNG，并行可选 1–8 段（默认 2 段），选择自动保存。实际并行不超过安全切分后的文件数；试用 4 段并行时，期望输出文件数也需至少 4 个。按完整订单和整行边界切分，所有文件沿用整批刀位。默认勾选“不限制并行内存预算”，不因预算降为串行；取消后才应用可设置的预算（初值 512MiB）。内存不足仍可能失败。每段均检查像素安全，失败/停止后本次输出标记为禁止打印并保留。报告包含实际并行段数和每段耗时；并行不保证提速，兼容状态栏的保存耗时包含分段合成与检查。

输出文件名带实际尺码：按生产顺序连续的 `S、M、L、XL` 简写为 `S-XL`；跳码、不连续或重复回到前一尺码时不冒充连续范围。保留原文件夹名、标签及段号，旋转文件标注“旋转区”或“常规+旋转区”。主界面和输出目录“切割说明.txt”列出各段文件、尺码、刀位、红线位置与换刀提醒。

打印参数可设置红色横向提示线，默认在区域最后一张图下方 3mm，线粗 0.3mm；换刀前及批次/分段结束处都会打印，并在实际预览展示。旋转区文件左侧刀码与标签默认一起右移 2mm，图片和刀位不动；普通区仍在左边缘。若标记碰到图片或红线重叠，禁止输出。刀码偏移是否令机器暂停必须实测，不作为可靠停机保护。

## Current features

The current UI focuses on local layout. Online order acceptance, batch creation,
and downloads are temporarily hidden; their implementation remains available.

- Recursively scan a folder for PNG, TIFF, JPEG, JFIF, WebP, or BMP images
- Set media width, spacing, margins, and DPI
- Preserve each image's physical print size using its embedded DPI
- Arrange images with a predictable shelf-layout algorithm
- Add configurable labels beside images using sequence numbers, dates, or filenames
- Detect QR membrane labels and align text beside them without adding row height
- Keep every cutter recognition color block on the left side of its image
- Preview label text and cutter color-block changes live in separate settings windows
- Choose 450/600 mm film and fixed-knife cutter layouts without rotating images
- Report physical print dimensions from embedded DPI and reject unknown sizes in cutter mode
- Preview and generate Longfeng CBT/non-CBT production batches with a final safety confirmation
- Download and automatically extract production-image archives
- Process each 12-digit production batch separately to avoid oversized canvases
- Combine the entire selected folder into one long PNG image
- Stream and save large PNG output with the multithreaded libvips engine
- Generate a JSON manifest with source files and placement coordinates

## Requirements

- Python 3.11 or 3.12
- Windows 10/11 for the production desktop build (development also works on macOS)

## Run locally

```bash
python -m venv .venv
```

Activate the environment:

```powershell
.venv\Scripts\Activate.ps1
```

Install and run:

```bash
pip install -r requirements.txt
python -m automatic_print
```

During development, use the auto-reloading launcher instead:

```bash
python dev.py
```

Keep that terminal open. When a Python source file changes, the running app closes
and immediately opens again with the new code. Closing the app yourself stops the
development launcher.

## Build a Windows executable

Run these commands on Windows:

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name AutomaticPrint automatic_print/__main__.py
```

The executable will be created under `dist/AutomaticPrint/`.

## Windows releases and updates

Production computers should install `AutomaticPrint-Setup.exe` from GitHub
Releases. They do not need Python, Git, or the source repository.

To prepare a tested release:

1. Update `automatic_print/__init__.py` with the approved version.
2. Commit the approved source.
3. Create and push a matching tag such as `v0.2.0`.
4. The Windows workflow builds the app and installer, then attaches it to a new
   GitHub Release.

The installed app checks for a newer approved Release in the background. Updates
are never installed silently: the user chooses whether to open the installer
download page.

## Fast iteration on one Windows test computer

During active development, one designated factory test computer can run the
source version instead of reinstalling every build.

### One-command setup and update

Open PowerShell on the test computer and run:

```powershell
powershell -ExecutionPolicy Bypass -Command "irm 'https://raw.githubusercontent.com/beijijizhou/automatic-print/main/windows/bootstrap-test-computer.ps1?v=0.1.188' | iex"
```

The script installs or checks Git, Python 3.12, and Google Chrome; clones or
updates the latest `main` source; creates the project virtual environment;
installs all requirements including Playwright; and starts the development app.
Run the same command again whenever a new approved change is pushed.

### Manual setup

1. Install Git for Windows and Python 3.12.
2. Clone this repository.
3. Double-click `windows/setup-dev.bat`.
4. Double-click `windows/run-dev.bat` and keep its terminal open.

For each approved test update, double-click `windows/update-dev.bat`. It pulls
the latest approved `main` commit and checks dependencies. The development
launcher detects changed Python files and restarts the app automatically.

Only the designated test computer should use this workflow. Production
computers should continue using tested GitHub Releases.

## Output

当前报告统一为 `排版报告.txt`：包含切割说明、总计/分步骤耗时、实际并行数与分段耗时，不再分别输出切割和耗时两个文本文件。旧报告保留。

打印参数 → 输出与并行默认启用“大图分块流式合成与保存”：超过64MiB原始RGBA的大图使用原生libvips流水线，不再转为整图NumPy数组或分配整图滤波缓冲。完整长图、透明度、DPI与分段选择不变。最终画布检查全部区域实际刀位通道及精确标记，保存后只核对PNG头、尺寸、格式与结束标记，不重复解压大图。无libvips时使用普通兼容画布；旧全数组编码不再由界面启用。原生延迟合成可能计入保存，报告明确标注，不冒充纯写盘耗时。

输出分辨率默认勾选“跟随原图DPI”，不强制插值放大到300 DPI。后台读取各图片内嵌DPI，一致时沿用原图实际DPI并保持毫米尺寸；同批混合DPI、缺可靠DPI或水平/垂直明显不一致时提示手动指定统一输出DPI。取消勾选即可使用记住的150/300等手动值；多批次分别跟随各自批次，多段输出使用整批同一DPI。报告和“复制耗时”显示实际输出DPI及跟随/手动模式。

平台字优先复用二维码旁经过源图透明像素检查的空位，不追加到图案右侧。没有安全空位时保守放在图片左侧外部，仍可能影响可并排宽度；不为省材料覆盖原图。旋转后重新检查，实际预览与输出共享坐标。

空位搜索覆盖整个膜标签高度带，不限二维码附近，动态适应左/右膜标签。双列总结和报告显示双排行数、常规单排及旋转单排数量；常规单排标记未达到全双排预期，并列出需要核对的图片及平台文字外置情况。

平台文字高度在主界面和标签设置中独立调整并显示，默认 6mm，0 表示自动二维码等高；设置持久保存，实际高度不超过二维码。调整已加载批次时后台刷新真实预览，不影响普通标签/序号字号；已有 PNG 需重新生成。

切膜模式优先把刀码和下方文字一起内置到原图最左侧透明区域，减少额外刀码列；没有安全空位时才外置。左右分区刀码固定识别基准不变，所有实际内置矩形重新核验源图透明像素，不能覆盖膜标签或图案。总结及报告显示刀码内置数量。

Each run creates a timestamped job folder containing:

```text
图片文件夹所在目录/
├── 批次123/
└── 切膜机文件/
    └── 批次123_JOB_YYYYMMDD_HHMMSS/
        ├── 批次123_标签名_S-XL 第001段.png
        ├── 排版报告.txt（切割说明与耗时合并）
        └── manifest.json
```

The first version deliberately keeps RIIN outside the application: it produces finished print canvases, and RIIN only needs to import them.
