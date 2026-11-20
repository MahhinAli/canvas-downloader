#!/usr/bin/env python3
"""Download every file from a Canvas course into a folder named after the course.

    python canvas_download.py              pick from a list of your courses
    python canvas_download.py 12345        by course id
    python canvas_download.py <course url> e.g. https://school.instructure.com/courses/12345
    python canvas_download.py all          every active course
    python canvas_download.py --setup      (re)create config.ini

Settings are looked up in this order (first one found wins):
  1. CANVAS_URL / CANVAS_TOKEN / CANVAS_SAVE_DIR environment variables
  2. config.ini next to this script (see config.example.ini)
  3. a .env file next to this script, or the one named by "env_file" in settings
  4. "base_url" / "token" in ~/.canvas_downloader.json (older versions)
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

HOME = os.path.expanduser("~")
SETTINGS_PATH = os.path.join(HOME, ".canvas_downloader.json")
DEFAULT_SAVE_DIR = os.path.join(HOME, "Canvas")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.ini")

# config.ini key -> internal name
CONFIG_KEYS = {"canvas_url": "CANVAS_URL", "api_token": "CANVAS_TOKEN", "save_folder": "CANVAS_SAVE_DIR"}

TOKEN_HELP = """\
How to get your Canvas access token:
  1. Log in to Canvas in your browser.
  2. Click "Account" (your profile picture, top left) -> "Settings".
  3. Scroll down to "Approved Integrations".
  4. Click "+ New Access Token".
  5. Purpose: anything, e.g. "file downloader". Expiry date is optional.
  6. Click "Generate Token" and copy it right away (Canvas only shows it once).

Treat the token like a password. It is saved only in config.ini on this
computer, which is in .gitignore so it never gets committed.
No "+ New Access Token" button? Your school has disabled student tokens;
ask your school's IT / Canvas admins.
"""


def read_env_file(path):
    values = {}
    if not path or not os.path.isfile(path):
        return values
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            values[key.strip()] = val.strip().strip("'\"")
    return values


def load_settings():
    settings = {}
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            settings = json.load(f)

    env = read_env_file(os.path.join(SCRIPT_DIR, ".env"))
    env.update(read_env_file(settings.get("env_file")))
    config = read_env_file(CONFIG_PATH)
    env.update({CONFIG_KEYS[k]: v for k, v in config.items() if k in CONFIG_KEYS and v})
    env.update({k: v for k, v in os.environ.items() if k.startswith("CANVAS_")})

    url = env.get("CANVAS_URL") or settings.get("base_url")
    token = env.get("CANVAS_TOKEN") or settings.get("token")
    if not url or not token:
        return None
    return {
        "base_url": url.rstrip("/"),
        "token": token,
        "save_dir": env.get("CANVAS_SAVE_DIR") or settings.get("save_dir") or DEFAULT_SAVE_DIR,
    }


def run_setup():
    print("Canvas downloader setup\n")
    print("Your Canvas URL is the address bar when logged in, up to the domain,")
    print("e.g. https://yourschool.instructure.com or https://canvas.yourschool.edu\n")
    url = ""
    while not url:
        url = input("Canvas URL: ").strip().rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    url = re.sub(r"(https?://[^/]+).*", r"\1", url)  # drop /courses/..., /login etc.

    print("\n" + TOKEN_HELP)
    token = ""
    while not token:
        token = input("Paste your access token: ").strip()
    save_dir = input(f"\nSave courses in [{DEFAULT_SAVE_DIR}]: ").strip()

    lines = [
        "# Canvas downloader settings - created by --setup.",
        "# Private: this file is in .gitignore. Never commit or share it.",
        "# See config.example.ini for what each setting means.",
        "",
        f"canvas_url = {url}",
        f"api_token = {token}",
        f"save_folder = {save_dir}",
        "",
    ]
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Saved to {CONFIG_PATH}\n")


class CanvasAPI:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.token = token

    def _open(self, url):
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + self.token})
        return urllib.request.urlopen(req, timeout=60)

    def get(self, path):
        with self._open(self.base_url + "/api/v1" + path) as resp:
            return json.load(resp)

    def get_all(self, path, **params):
        """Follow Canvas's Link-header pagination and return every item."""
        params.setdefault("per_page", 100)
        url = self.base_url + "/api/v1" + path + "?" + urllib.parse.urlencode(params, doseq=True)
        items = []
        while url:
            with self._open(url) as resp:
                page = json.load(resp)
                items.extend(page if isinstance(page, list) else [page])
                url = next_page(resp.headers.get("Link", ""))
        return items


def next_page(link_header):
    m = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
    return m.group(1) if m else None


def clean_filename(name):
    # Windows is the pickiest, so strip whatever it doesn't allow.
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip().rstrip(".")
    return name[:150] or "untitled"


def fetch(url, dest, size=None):
    if os.path.exists(dest) and (size is None or os.path.getsize(dest) == size):
        return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    # File urls already include a verifier and redirect to S3, which rejects
    # requests that also carry our bearer token - so no auth header here.
    tmp = dest + ".part"
    with urllib.request.urlopen(url, timeout=120) as resp, open(tmp, "wb") as out:
        while True:
            chunk = resp.read(256 * 1024)
            if not chunk:
                break
            out.write(chunk)
    os.replace(tmp, dest)
    return True


def download_course(api, course, save_dir):
    course_id = course["id"]
    course_dir = os.path.join(save_dir, clean_filename(course["name"]))
    print(f"\n{course['name']}\n  -> {course_dir}")

    done = set()
    new = have = failed = 0

    def save(f, subdir=""):
        nonlocal new, have, failed
        if f["id"] in done or not f.get("url"):
            return
        done.add(f["id"])
        dest = os.path.join(course_dir, subdir, clean_filename(f["display_name"]))
        try:
            if fetch(f["url"], dest, f.get("size")):
                new += 1
                print("  +", os.path.relpath(dest, course_dir))
            else:
                have += 1
        except (urllib.error.URLError, OSError) as e:
            failed += 1
            print(f"  ! {f['display_name']}: {e}")

    # The Files tab, keeping the instructor's folder layout.
    try:
        folders = {fo["id"]: fo["full_name"] for fo in api.get_all(f"/courses/{course_id}/folders")}
        for f in api.get_all(f"/courses/{course_id}/files"):
            path = re.sub(r"^course files/?", "", folders.get(f["folder_id"], ""))
            subdir = os.path.join(*map(clean_filename, path.split("/"))) if path else ""
            save(f, subdir)
    except urllib.error.HTTPError as e:
        print(f"  Files tab not available (HTTP {e.code}), trying modules")

    # Lots of courses hide the Files tab and only link files from modules.
    try:
        for module in api.get_all(f"/courses/{course_id}/modules", **{"include[]": "items"}):
            items = module.get("items")
            if items is None:  # Canvas leaves these out for big modules
                items = api.get_all(f"/courses/{course_id}/modules/{module['id']}/items")
            for item in items:
                if item.get("type") != "File" or item.get("content_id") in done:
                    continue
                try:
                    f = api.get(f"/courses/{course_id}/files/{item['content_id']}")
                except urllib.error.HTTPError:
                    continue
                save(f, os.path.join("Modules", clean_filename(module["name"])))
    except urllib.error.HTTPError as e:
        print(f"  Modules not available (HTTP {e.code})")

    print(f"  {new} new, {have} already downloaded, {failed} failed")


def pick_courses(api, courses, choice):
    if choice.lower() == "all":
        return courses
    if choice.isdigit() and len(choice) <= 3 and 1 <= int(choice) <= len(courses):
        return [courses[int(choice) - 1]]
    m = re.search(r"/courses/(\d+)", choice)
    course_id = m.group(1) if m else choice
    if not course_id.isdigit():
        return []
    return [api.get(f"/courses/{course_id}")]


def main(args):
    if "--setup" in args:
        run_setup()
        args = [a for a in args if a != "--setup"]

    settings = load_settings()
    if settings is None:
        run_setup()
        settings = load_settings()

    api = CanvasAPI(settings["base_url"], settings["token"])
    try:
        courses = [c for c in api.get_all("/courses", enrollment_state="active") if c.get("name")]
    except urllib.error.HTTPError as e:
        print(f"Canvas refused the login (HTTP {e.code}). Check your URL and token, or run with --setup.")
        return 1

    if args:
        choice = args[0]
    else:
        for i, c in enumerate(courses, 1):
            print(f"{i:>3}. {c['name']}")
        choice = input("\nCourse number, link, or 'all': ").strip()

    selected = pick_courses(api, courses, choice)
    if not selected:
        print("Couldn't work out which course you meant.")
        return 1

    for course in selected:
        download_course(api, course, settings["save_dir"])
    return 0


if __name__ == "__main__":
    status = main(sys.argv[1:])
    # Keep the window open when started by double-clicking on Windows.
    if os.name == "nt" and len(sys.argv) == 1:
        input("\nPress Enter to close...")
    sys.exit(status)
