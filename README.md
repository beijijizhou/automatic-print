# Automatic Print

Windows desktop application for combining a folder of images into print-ready layout canvases that can be imported directly into RIIN or another RIP application.

## Current features

- Recursively scan a folder for PNG, TIFF, JPEG, JFIF, WebP, or BMP images
- Set media width, spacing, margins, and DPI
- Preserve each image's physical print size using its embedded DPI
- Arrange images with a predictable shelf-layout algorithm
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

One-time setup:

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
