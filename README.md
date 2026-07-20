# Automatic Print

Windows desktop application for combining a folder of images into print-ready layout canvases that can be imported directly into RIIN or another RIP application.

## Current features

- Select a folder containing PNG, TIFF, JPEG, or WebP images
- Set media width, spacing, margins, and DPI
- Preserve each image's physical print size using its embedded DPI
- Arrange images with a predictable shelf-layout algorithm
- Combine the entire selected folder into one long PNG image
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

## Build a Windows executable

Run these commands on Windows:

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name AutomaticPrint automatic_print/__main__.py
```

The executable will be created under `dist/AutomaticPrint/`.

## Output

Each run creates a timestamped job folder containing:

```text
output/
└── JOB_YYYYMMDD_HHMMSS/
    ├── print.png
    └── manifest.json
```

The first version deliberately keeps RIIN outside the application: it produces finished print canvases, and RIIN only needs to import them.
