# canvas-downloader

Grab every file from a Canvas course in one go. Each course gets its own folder,
named after the course, with the same folder layout as the course's Files page.

If the instructor hid the Files tab (which happens a lot), it also picks up files
linked from Modules and puts them under `Modules/<module name>/`.

No dependencies, just Python 3.8+.

## Quick start

```
git clone https://github.com/MahhinAli/canvas-downloader.git
cd canvas-downloader
python canvas_download.py
```

The first time you run it, it asks for your Canvas URL and an access token and
saves them to `~/.canvas_downloader.json`. After that it shows a numbered list of
your courses and you pick one.

## Usage

```
python canvas_download.py              # pick from a list
python canvas_download.py 12345        # by course id
python canvas_download.py https://school.instructure.com/courses/12345
python canvas_download.py all          # every active course
python canvas_download.py --setup      # change your URL / token / save folder
```

On Windows you can double-click `canvas-download.bat`.

Files are saved to `~/Canvas/<Course Name>/`. Running it again only downloads
files you don't already have (it compares file sizes), so it's safe to rerun
every week to pick up new slides.

## Using it with your own school's Canvas

Nothing in the script is tied to a particular university. It only needs two things.

### 1. Your Canvas URL

This is whatever you see in the address bar when you're logged in to Canvas, up
to the first `/`. Some examples:

| School setup | URL to use |
| --- | --- |
| Hosted by Instructure | `https://yourschool.instructure.com` |
| Custom domain | `https://canvas.yourschool.edu` |
| Self-hosted | whatever your school uses, e.g. `https://lms.yourschool.ac.uk` |

Leave off `/courses/...`, `/login`, and any trailing slash.

### 2. An access token

1. Log in to Canvas and open **Account → Settings**.
2. Scroll to **Approved Integrations** and click **+ New Access Token**.
3. Give it a name (e.g. "file downloader") and, optionally, an expiry date.
4. Copy the token straight away. Canvas only shows it once.

The token acts as you, so it can see exactly what you can see in Canvas, nothing more.
Treat it like a password. If it ever leaks, delete it on the same settings page.

> If there's no **New Access Token** button, your school has turned off personal
> tokens for students. The script can't work around that. You'd have to ask your
> school's IT or Canvas admins.

### Where to put them

Pick whichever suits you. They're checked in this order:

1. **Environment variables:** `CANVAS_URL` and `CANVAS_TOKEN`. Handy for scripts
   and scheduled tasks.
2. **A `.env` file** next to `canvas_download.py`. Copy `.env.example` to `.env`
   and fill it in. `.env` is in `.gitignore`, so it won't get committed.
3. **`~/.canvas_downloader.json`**, the file `--setup` writes. You can also point it at
   a `.env` that lives somewhere else:

   ```json
   {
     "env_file": "/path/to/some/other/.env",
     "save_dir": "/path/to/save/courses"
   }
   ```

### Changing where files go

Set `CANVAS_SAVE_DIR` (in the environment or `.env`), or `save_dir` in
`~/.canvas_downloader.json`. Each course still gets its own subfolder.

## Tweaking the script

A few spots you might want to change, all in `canvas_download.py`:

- **Which courses show up:** `main()` asks for `enrollment_state="active"`. Remove
  that argument to also list concluded courses (if your school still gives you
  access to them).
- **Folder names:** `download_course()` builds the folder from `course["name"]`.
  Use `course["course_code"]` instead if you prefer short codes.
- **Filename rules:** `clean_filename()` removes characters Windows doesn't allow
  and caps names at 150 characters.
- **Module files:** the second half of `download_course()` handles files linked from
  Modules. Delete it if you only want the Files tab.

## Limitations

- Files that are only linked inside page or assignment text aren't picked up.
- External links (Google Drive, YouTube, etc.) are ignored.
- Some schools don't let students create access tokens (see above).
- Please respect your course's copyright rules. This is meant for keeping your own
  copies of materials you already have access to.
