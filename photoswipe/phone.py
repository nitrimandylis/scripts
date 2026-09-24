# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["pymobiledevice3"]
# ///
"""Read the iPhone's camera roll over USB and save a list of its files to data/phone.json.

Plug in the iPhone, unlock it, trust this Mac, then: uv run phone.py
"""
import asyncio
import json
import os

from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.afc import AfcService

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PHONE_FILE = os.path.join(DATA, "phone.json")


async def main():
    lockdown = await create_using_usbmux()
    files = []
    async with AfcService(lockdown=lockdown) as afc:
        async for path in afc.dirlist("/DCIM", -1):
            info = await afc.stat(path)
            if info["st_ifmt"] != "S_IFREG":
                continue
            # .AAE files are edit sidecars, not photos
            if path.upper().endswith(".AAE"):
                continue
            files.append({
                "name": path.split("/")[-1],
                "size": info["st_size"],
                "date": info["st_mtime"].isoformat(),
            })

    os.makedirs(DATA, exist_ok=True)
    with open(PHONE_FILE, "w") as f:
        json.dump(files, f, indent=1)
    print(f"saved {len(files)} files from the iPhone to data/phone.json")


asyncio.run(main())
