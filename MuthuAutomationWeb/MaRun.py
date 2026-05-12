__version__ = "2026.05.12.01"
__author__ = "Muthukumar Subramanian"

"""
MaRun – Platform-Aware Launcher for MuthuAutomation Website

Detects the host platform at startup, auto-installs all dependencies
from requirements.txt, and launches MaManager with the correct
server strategy for the environment.
"""

import os
import platform


def is_android() -> tuple[bool, str]:
    if os.environ.get("TERMUX_VERSION"):
        return True, "termux"
    if os.path.exists("/data/data/com.termux"):
        return True, "termux"
    if os.path.exists("/data/data/ru.iiec.pydroid3"):
        return True, "pydroid"
    if os.path.exists("/system/build.prop"):
        return True, "android"
    return False, ""


android, _ = is_android()
if platform.system() == "Windows" and not android:
    try:
        import eventlet

        eventlet.monkey_patch()
    except ImportError:
        pass

import re
import sys
import time
import signal
import logging
import subprocess
import importlib.util

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

IMPORT_NAME_MAP = {
    "Flask-SocketIO": "flask_socketio",
    "flask-socketio": "flask_socketio",
    "gevent-websocket": "geventwebsocket",
}


def ensure_package(package_name: str):
    import_name = IMPORT_NAME_MAP.get(package_name, package_name)
    if importlib.util.find_spec(import_name) is not None:
        logging.info(f"Already installed: {package_name} ✔")
        return

    logging.info(f"Installing: {package_name} ...")
    base_cmd = [sys.executable, "-m", "pip", "install", package_name]

    try:
        subprocess.check_call(base_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info(f"Installed:  {package_name} ✔")
    except subprocess.CalledProcessError:
        logging.info(f"Retrying with --break-system-packages: {package_name}")
        try:
            subprocess.check_call(base_cmd + ["--break-system-packages"], stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            logging.info(f"Installed:  {package_name} ✔")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to install '{package_name}': {e}")


ANDROID_SKIP_PACKAGES = {"gevent", "gevent-websocket", "gunicorn"}


def install_from_requirements(req_file: str = "requirements.txt"):
    req_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), req_file)
    if not os.path.exists(req_path):
        return
    logging.info(f"── Checking requirements from {req_file} ──")
    android_mode, _ = is_android()
    with open(req_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            pkg_name = re.split(r"[>=<!~\s]", line)[0].strip()
            if not pkg_name: continue
            if android_mode and pkg_name in ANDROID_SKIP_PACKAGES: continue
            ensure_package(pkg_name)


def is_windows() -> bool: return platform.system().lower() == "windows"


def is_render() -> bool: return os.environ.get("RENDER", "false").lower() == "true"


def free_port(port: int):
    try:
        pids = subprocess.check_output(f"lsof -t -i:{port}", shell=True).decode().split()
        for pid in pids:
            os.kill(int(pid), signal.SIGKILL)
            time.sleep(0.5)
    except Exception:
        pass


def _run_socketio(ma, port: int):
    logging.info(f"[🌐] http://127.0.0.1:{port}")
    ma.socketio.run(ma.app, host="0.0.0.0", port=port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    if not is_render():
        install_from_requirements("requirements.txt")

    import MaManager as ma

    if is_windows():
        _run_socketio(ma, port)
    else:
        android_mode, _ = is_android()
        if android_mode:
            _run_socketio(ma, port)
        else:
            if not is_render(): free_port(port)
            if os.environ.get("FLASK_ENV") == "production" or is_render():
                subprocess.run(
                    ["gunicorn", "-k", "geventwebsocket.gunicorn.workers.GeventWebSocketWorker", "-w", "1", "-b",
                     f"0.0.0.0:{port}", "MaManager:app"])
            else:
                _run_socketio(ma, port)
