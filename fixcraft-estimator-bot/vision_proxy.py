import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Optional
from uuid import uuid4


PUBLIC_DIR = Path(os.getenv("VISION_PUBLIC_DIR", "/Users/vladimirprihodko/.hermes/fixcraft-estimator-public"))
PORT = int(os.getenv("VISION_PUBLIC_PORT", "8765"))
NGROK_BIN = os.getenv("NGROK_BIN", "/Users/vladimirprihodko/bin/ngrok")
NGROK_API = os.getenv("NGROK_API", "http://127.0.0.1:4040/api/tunnels")


def ensure_public_dir() -> Path:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    index = PUBLIC_DIR / "index.html"
    if not index.exists():
        index.write_text("FixCraft Estimator image host OK\n")
    return PUBLIC_DIR


def port_open(host="127.0.0.1", port=PORT, timeout=0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def start_static_server_if_needed() -> bool:
    ensure_public_dir()
    if port_open(port=PORT):
        return False
    logs = Path.home() / "logs"
    logs.mkdir(exist_ok=True)
    out = open(logs / "fixcraft-estimator-static-server.out.log", "ab", buffering=0)
    err = open(logs / "fixcraft-estimator-static-server.err.log", "ab", buffering=0)
    subprocess.Popen(
        ["/usr/bin/python3", "-m", "http.server", str(PORT), "--directory", str(PUBLIC_DIR)],
        stdout=out,
        stderr=err,
        start_new_session=True,
    )
    for _ in range(20):
        if port_open(port=PORT):
            return True
        time.sleep(0.25)
    raise RuntimeError(f"Static server did not start on port {PORT}")


def get_ngrok_url() -> Optional[str]:
    try:
        with urllib.request.urlopen(NGROK_API, timeout=3) as r:
            data = json.load(r)
        urls = [t.get("public_url") for t in data.get("tunnels", []) if t.get("public_url", "").startswith("https://")]
        return urls[0] if urls else None
    except Exception:
        return None


def start_ngrok_if_needed() -> str:
    url = os.getenv("VISION_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if url:
        return url
    existing = get_ngrok_url()
    if existing:
        return existing.rstrip("/")
    if not Path(NGROK_BIN).exists():
        raise RuntimeError(f"ngrok not found at {NGROK_BIN}")
    logs = Path.home() / "logs"
    logs.mkdir(exist_ok=True)
    out = open(logs / "fixcraft-estimator-ngrok.out.log", "ab", buffering=0)
    err = open(logs / "fixcraft-estimator-ngrok.err.log", "ab", buffering=0)
    subprocess.Popen(
        [NGROK_BIN, "http", str(PORT), "--log=stdout"],
        stdout=out,
        stderr=err,
        start_new_session=True,
    )
    for _ in range(40):
        url = get_ngrok_url()
        if url:
            return url.rstrip("/")
        time.sleep(0.5)
    raise RuntimeError("ngrok tunnel did not start")


def ensure_public_base_url() -> str:
    start_static_server_if_needed()
    return start_ngrok_if_needed()


def publish_image(local_path, suffix=None) -> str:
    ensure_public_dir()
    local_path = Path(local_path)
    ext = suffix or local_path.suffix or ".jpg"
    safe_name = f"{int(time.time())}-{uuid4().hex}{ext}"
    dest = PUBLIC_DIR / safe_name
    shutil.copy2(local_path, dest)
    base = ensure_public_base_url()
    return f"{base}/{safe_name}"


def cleanup_old_images(max_age_hours: int = 24) -> int:
    ensure_public_dir()
    cutoff = time.time() - max_age_hours * 3600
    removed = 0
    for p in PUBLIC_DIR.iterdir():
        if p.is_file() and p.name != "index.html" and p.stat().st_mtime < cutoff:
            p.unlink(missing_ok=True)
            removed += 1
    return removed
