# Automatic Print

Windows desktop application for combining a folder of images into print-ready layout canvases that can be imported directly into RIIN or another RIP application.

## 测试电脑一键安装或更新

在测试电脑上打开 PowerShell，复制并运行：

```powershell
powershell -ExecutionPolicy Bypass -Command "irm 'https://raw.githubusercontent.com/beijijizhou/automatic-print/main/windows/bootstrap-test-computer.ps1?v=0.1.16' | iex"
```

同一条命令既可首次安装，也可在以后下载最新代码并更新运行环境。
它会自动准备 Git、Python 3.12、Google Chrome、Playwright 及项目所需依赖，
然后启动开发版程序。

## Current features

- Recursively scan a folder for PNG, TIFF, JPEG, JFIF, WebP, or BMP images
- Set media width, spacing, margins, and DPI
- Preserve each image's physical print size using its embedded DPI
- Arrange images with a predictable shelf-layout algorithm
- Add configurable labels beside images using sequence numbers, dates, or filenames
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
powershell -ExecutionPolicy Bypass -Command "irm 'https://raw.githubusercontent.com/beijijizhou/automatic-print/main/windows/bootstrap-test-computer.ps1?v=0.1.16' | iex"
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

Each run creates a timestamped job folder containing:

```text
output/
└── JOB_YYYYMMDD_HHMMSS/
    ├── print.png
    └── manifest.json
```

The first version deliberately keeps RIIN outside the application: it produces finished print canvases, and RIIN only needs to import them.
