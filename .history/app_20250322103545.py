#!/usr/bin/env python3

from flask import Flask, render_template, request, send_file
from flask_socketio import SocketIO, emit
import asyncio
import aiohttp
import zipfile
import os
from pathlib import Path
import threading

app = Flask(__name__)
socketio = SocketIO(app, async_mode="eventlet")

# Define the base directory for ROMs and BIOS
roms_base_dir = Path.home() / "roms"

# Dictionary mapping system names to their archive.org URLs and target directories
systems = {
    1: {"name": "Nintendo NES", "url": "https://archive.org/download/retro-roms-best-set/Nintendo%20-%20NES.zip", "dir": "nes"},
    2: {"name": "Nintendo SNES", "url": "https://archive.org/download/retro-roms-best-set/Nintendo%20-%20SNES.zip", "dir": "snes"},
    3: {"name": "Nintendo Game Boy", "url": "https://archive.org/download/retro-roms-best-set/Nintendo%20-%20Game%20Boy.zip", "dir": "gb"},
    4: {"name": "Nintendo Game Boy Color", "url": "https://archive.org/download/retro-roms-best-set/Nintendo%20-%20Game%20Boy%20Color.zip", "dir": "gbc"},
    5: {"name": "Nintendo Game Boy Advance", "url": "https://archive.org/download/retro-roms-best-set/Nintendo%20-%20Game%20Boy%20Advance.zip", "dir": "gba"},
    6: {"name": "Nintendo N64", "url": "https://archive.org/download/retro-roms-best-set/Nintendo%20-%20N64.zip", "dir": "n64"},
    7: {"name": "Nintendo DS", "url": "https://archive.org/download/retro-roms-best-set/Nintendo%20-%20DS.zip", "dir": "nds"},
    8: {"name": "Sega Genesis", "url": "https://archive.org/download/retro-roms-best-set/Sega%20-%20Genesis.zip", "dir": "genesis"},
    9: {"name": "Sega Master System", "url": "https://archive.org/download/retro-roms-best-set/Sega%20-%20Master%20System.zip", "dir": "sms"},
    10: {"name": "Sega Game Gear", "url": "https://archive.org/download/retro-roms-best-set/Sega%20-%20Game%20Gear.zip", "dir": "gg"},
    11: {"name": "Sony PlayStation 1 (A-L)", "url": "https://archive.org/download/retro-roms-best-set/Sony%20-%20PS1%20%28A-L%29.zip", "dir": "psx"},
    12: {"name": "Sony PlayStation 1 (L-Z)", "url": "https://archive.org/download/retro-roms-best-set/Sony%20-%20PS1%20%28L-Z%29.zip", "dir": "psx"},
    13: {"name": "Arcade (MAME 2003 Plus)", "url": "https://archive.org/download/retro-roms-best-set/Arcade%20-%20Mame%202003%20Plus.zip", "dir": "mame"},
    14: {"name": "All BIOS", "url": "https://archive.org/download/retroarch-bios-pack/Retroarch%20Bios%20Pack.zip", "dir": "bios"},
}

# Store download progress
download_status = {}

async def download_file(session, url, target_path, filename, system_id):
    """Asynchronously download a file with progress updates via WebSocket."""
    zip_file = target_path / filename
    target_path.mkdir(parents=True, exist_ok=True)
    
    socketio.emit("progress", {"system_id": system_id, "status": "Downloading", "progress": 0})
    
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            
            with open(zip_file, "wb") as f:
                async for chunk in response.content.iter_chunked(8192):
                    downloaded += len(chunk)
                    f.write(chunk)
                    if total_size > 0:
                        progress = int((downloaded / total_size) * 100)
                        socketio.emit("progress", {"system_id": system_id, "status": "Downloading", "progress": progress})
            
            socketio.emit("progress", {"system_id": system_id, "status": "Extracting", "progress": 100})
            with zipfile.ZipFile(zip_file, "r") as zip_ref:
                zip_ref.extractall(target_path)
            os.remove(zip_file)
            
            socketio.emit("progress", {"system_id": system_id, "status": "Completed", "progress": 100})
            return zip_file
    except Exception as e:
        socketio.emit("progress", {"system_id": system_id, "status": f"Error: {str(e)}", "progress": 0})
        return None

@app.route("/")
def index():
    return render_template("index.html", systems=systems)

@app.route("/download/<int:system_id>")
def download(system_id):
    if system_id not in systems:
        return "Invalid system ID", 404
    
    system = systems[system_id]
    filename = f"{system['name'].replace(' ', '_')}.zip"
    target_dir = system["dir"]
    
    # Start download in a separate thread with asyncio
    def run_download():
        asyncio.run(start_download(system_id, system["url"], target_dir, filename))
    
    threading.Thread(target=run_download).start()
    return "Download started. Check progress on the page.", 200

async def start_download(system_id, url, target_dir, filename):
    async with aiohttp.ClientSession() as session:
        await download_file(session, url, roms_base_dir / target_dir, filename, system_id)

@socketio.on("connect")
def handle_connect():
    emit("update", {"message": "Connected to the RetroArch Downloader"})

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5003, debug=True)