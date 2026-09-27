# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["osxphotos"]
# ///
"""Swipe through the Photos library in the browser.

Run: uv run app.py   then open http://localhost:8765 in Safari.
Rejected items go into a Photos album called "To delete". Nothing is deleted here.
"""
import datetime
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import osxphotos
from osxphotos.photosalbum import PhotosAlbum

PORT = 8765
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)
PROGRESS_FILE = os.path.join(DATA, "progress.json")
PHONE_FILE = os.path.join(DATA, "phone.json")
ALBUM_NAME = "To delete"


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"choices": {}, "pushed": []}


def save_progress():
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=1)


def card(photo):
    return {
        "uuid": photo.uuid,
        "video": photo.ismovie,
        "size": photo.original_filesize,
        "date": photo.date.strftime("%d %b %Y, %H:%M"),
        "name": photo.original_filename,
    }


def build_decks(photos):
    """Split the library into the three decks. Each item lands in the first deck that fits."""
    gone_from_iphone = []
    if os.path.exists(PHONE_FILE):
        with open(PHONE_FILE) as f:
            phone_files = json.load(f)
        phone_sizes = set(item["size"] for item in phone_files)
        phone_names = set(item["name"] for item in phone_files)
        oldest = min(datetime.date.fromisoformat(item["date"][:10]) for item in phone_files)
        # Only photos from the phone's date range can be compared against it.
        # A photo still on the phone matches by exact file size or by file name.
        for photo in photos:
            if photo.date.date() < oldest:
                continue
            if photo.original_filesize in phone_sizes or photo.original_filename in phone_names:
                continue
            gone_from_iphone.append(photo)
        print(f"phone.json: {len(phone_files)} files, oldest {oldest}, "
              f"{len(gone_from_iphone)} Mac items from that range are gone from the phone")

    taken = set(photo.uuid for photo in gone_from_iphone)
    videos = [p for p in photos if p.ismovie and p.uuid not in taken]
    videos.sort(key=lambda p: p.original_filesize, reverse=True)
    taken.update(p.uuid for p in videos)
    rest = [p for p in photos if p.uuid not in taken]
    rest.sort(key=lambda p: p.date)

    return {
        "iphone": [card(p) for p in gone_from_iphone],
        "videos": [card(p) for p in videos],
        "rest": [card(p) for p in rest],
    }


print("reading the Photos library...")
db = osxphotos.PhotosDB()
# Shared-album items are not really in the library and cannot be deleted from it.
photos = [p for p in db.photos() if not p.shared]
by_uuid = {p.uuid: p for p in photos}
decks = build_decks(photos)
progress = load_progress()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # keep the terminal quiet

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/state":
            self.send_json({"decks": decks, "progress": progress})
        elif self.path.startswith("/media/"):
            uuid = self.path[len("/media/"):]
            photo = by_uuid.get(uuid)
            if photo is None:
                self.send_error(404)
                return
            self.send_media(photo)
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length) or b"{}")

        if self.path == "/api/decide":
            uuid = data["uuid"]
            if uuid in progress["pushed"]:
                self.send_json({"error": "already in the album, remove it there"}, 400)
                return
            if data["choice"] == "undo":
                progress["choices"].pop(uuid, None)
            else:
                progress["choices"][uuid] = data["choice"]
            save_progress()
            self.send_json({"ok": True})

        elif self.path == "/api/push":
            to_push = []
            for uuid, choice in progress["choices"].items():
                if choice == "delete" and uuid not in progress["pushed"]:
                    to_push.append(uuid)
            if to_push:
                try:
                    album = PhotosAlbum(ALBUM_NAME)
                    album.extend([by_uuid[uuid] for uuid in to_push])
                except Exception as error:
                    print(f"push failed: {error!r}")
                    self.send_json({"error": repr(error)}, 500)
                    return
                progress["pushed"].extend(to_push)
                save_progress()
            self.send_json({"pushed": len(to_push)})

        else:
            self.send_error(404)

    def send_media(self, photo):
        if photo.ismovie:
            path = photo.path
            content_type = "video/quicktime" if path.lower().endswith(".mov") else "video/mp4"
        elif photo.path_derivatives:
            # Photos keeps JPEG previews; the first one is the biggest
            path = photo.path_derivatives[0]
            content_type = "image/jpeg"
        else:
            path = photo.path
            content_type = "image/heic" if path.lower().endswith(".heic") else "image/jpeg"

        if path is None or not os.path.exists(path):
            self.send_error(404)
            return

        # Safari only plays video if the server answers Range requests
        # ("give me bytes 0-1023"), so handle those by hand.
        file_size = os.path.getsize(path)
        start = 0
        end = file_size - 1
        range_header = self.headers.get("Range")
        if range_header and range_header.startswith("bytes="):
            first, last = range_header[len("bytes="):].split("-")
            if first:
                start = int(first)
                if last:
                    end = min(int(last), file_size - 1)
            else:
                # "bytes=-500" means the last 500 bytes
                start = file_size - int(last)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        else:
            self.send_response(200)

        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()

        remaining = end - start + 1
        try:
            with open(path, "rb") as f:
                f.seek(start)
                while remaining > 0:
                    chunk = f.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the browser skipped ahead, that's fine


counts = ", ".join(f"{name} {len(items)}" for name, items in decks.items())
print(f"decks: {counts}")
print(f"open http://localhost:{PORT} in Safari")
ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
