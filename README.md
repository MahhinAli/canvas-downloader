# canvas-downloader

Grab every file from a Canvas course in one go. Each course gets its own folder,
named after the course, with the same folder layout as the course's Files page.

If the instructor hid the Files tab (which happens a lot), it also picks up files
linked from Modules and puts them under `Modules/<module name>/`.

No dependencies, just Python 3.8+.

## Setup

1. In Canvas go to **Account → Settings → + New Access Token** and copy the token.
2. Copy `.env.example` to `.env` and fill in `CANVAS_URL` and `CANVAS_TOKEN`.

You can also set them as environment variables, or just run the script and it will
ask you for them.

## Usage

```
python canvas_download.py              # pick from a list
python canvas_download.py 12345        # by course id
python canvas_download.py https://school.instructure.com/courses/12345
python canvas_download.py all          # every active course
```

On Windows you can double-click `canvas-download.bat`.

Files are saved to `~/Canvas/<Course Name>/` unless you set `CANVAS_SAVE_DIR`.
Running it again only downloads files you don't already have.

## Limitations

- Files that are only linked inside page or assignment text aren't picked up.
- External links (Google Drive, YouTube, etc.) are ignored.
- Some schools don't let students create access tokens.
