from __future__ import annotations

import json
import os
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


@dataclass
class RootDirectorySize:
    name: str
    path: str
    bytes: int


def iter_files_safe(base_path: Path):
    for root, _, files in os.walk(base_path, onerror=lambda _: None):
        root_path = Path(root)
        for filename in files:
            yield root_path / filename


def get_directory_size_bytes(directory: Path) -> int:
    total = 0
    for file_path in iter_files_safe(directory):
        try:
            if not file_path.is_symlink():
                total += file_path.stat().st_size
        except OSError:
            continue
    return total


def list_disks() -> list[dict[str, str]]:
    if os.name == "nt":
        drives = []
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            mount = f"{letter}:\\"
            if os.path.exists(mount):
                drives.append({"mountpoint": mount, "label": mount})
        return drives

    mounts: list[dict[str, str]] = []
    try:
        with open("/proc/mounts", "r", encoding="utf-8") as mounts_file:
            seen = set()
            for line in mounts_file:
                parts = line.split()
                if len(parts) < 3:
                    continue
                mountpoint = parts[1]
                fstype = parts[2]
                if fstype in {"proc", "sysfs", "tmpfs", "devtmpfs", "devpts", "cgroup", "cgroup2", "overlay", "squashfs", "mqueue"}:
                    continue
                if mountpoint.startswith(("/proc", "/sys", "/dev")):
                    continue
                if mountpoint not in seen:
                    seen.add(mountpoint)
                    mounts.append({"mountpoint": mountpoint, "label": mountpoint})
    except FileNotFoundError:
        mounts = [{"mountpoint": "/", "label": "/"}]

    return sorted(mounts or [{"mountpoint": "/", "label": "/"}], key=lambda item: item["mountpoint"])


def scan_root_directories(mountpoint: str) -> list[RootDirectorySize]:
    root_path = Path(mountpoint)
    entries: list[RootDirectorySize] = []
    try:
        for child in root_path.iterdir():
            try:
                if child.is_symlink():
                    continue
                if child.is_file():
                    size = child.stat().st_size
                elif child.is_dir():
                    size = get_directory_size_bytes(child)
                else:
                    continue
                entries.append(RootDirectorySize(name=child.name, path=str(child), bytes=size))
            except OSError:
                continue
    except OSError:
        return []

    return sorted(entries, key=lambda item: item.bytes, reverse=True)


class TreeSizeHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/disks":
            return self._send_json({"disks": list_disks()})
        if parsed.path == "/":
            self.path = "/templates/index.html"
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/scan":
            self.send_error(404, "Not Found")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length) if content_length else b"{}"

        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return self._send_json({"error": "JSON invalide."}, status_code=400)

        selected_mounts = payload.get("mountpoints", [])
        if not isinstance(selected_mounts, list) or not selected_mounts:
            return self._send_json({"error": "Veuillez sélectionner au moins un lecteur."}, status_code=400)

        result = []
        for mountpoint in selected_mounts:
            entries = scan_root_directories(mountpoint)
            result.append(
                {
                    "mountpoint": mountpoint,
                    "totalBytes": sum(item.bytes for item in entries),
                    "entries": [
                        {"name": item.name, "path": item.path, "bytes": item.bytes}
                        for item in entries
                    ],
                }
            )

        return self._send_json({"scans": result})

    def _send_json(self, payload: dict, status_code: int = 200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 8000), TreeSizeHandler)
    print("TreeSize disponible sur http://localhost:8000")
    server.serve_forever()
