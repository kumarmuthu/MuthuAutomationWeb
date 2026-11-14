__version__ = "2026.05.12.01"
__author__ = "Muthukumar Subramanian"

"""
MaRun – Platform-Aware Launcher for MuthuAutomation Website

Detects the host platform at startup, auto-installs all dependencies
from requirements.txt, and launches MaManager with the correct
server strategy for the environment.
"""

# FIRST, before importing anything else. eventlet replaces socket/threading/time with its own
# versions, and it can only replace what has not been used yet -- so monkey_patch() either runs
# before the other imports, or it has to go back and upgrade objects those imports already made.
#
# That second path is what used to happen here (os and platform were imported above it), and on
# Windows it failed loudly every run:
#
#   An exception was thrown while monkey_patching for eventlet.
#   ffi.error: symbol 'RtlNtStatusToDosError' not found in library 'kernel32.dll'
#   ffi.error: symbol 'CancelIoEx' not found in library 'ntdll.dll'
#
# eventlet's _upgrade_instances() walks already-created objects and calls vars() on each one.
# On a cffi library object that triggers cffi's lazy symbol lookup against the wrong DLL (both
# symbols above are reported against the library the OTHER one lives in). eventlet catches it
# and carries on, so the app still starts -- but the patch is only partly applied, which is a
# worse state to run in than either fully patched or not patched at all.
#
# Only os and sys are imported above the patch, and only because the interpreter has ALREADY
# imported both before any of this runs -- site.py uses them during startup. So naming them here
# binds names that exist either way and creates nothing new for eventlet to upgrade. Everything
# else (platform, subprocess, logging, ...) stays below, which is the whole point.
#
# sys.platform rather than platform.system(): same answer, without having to import platform
# above the patch. The Android check is kept explicit anyway -- Termux and Pydroid do report
# 'linux' rather than 'win32', so it is redundant today, but that is a property of how those
# two happen to identify themselves, not something this file should quietly depend on.
import os
import sys


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
if sys.platform == "win32" and not android:
    # THIS LINE is the actual Windows fix, and it must come before `import eventlet`.
    #
    # eventlet imports dnspython for its greendns resolver, dnspython imports trio, and
    # trio._core._windows_cffi builds a cffi library whose symbols span BOTH kernel32 and
    # ntdll. monkey_patch() then walks live objects and calls vars() on that cffi lib, which
    # makes cffi resolve every symbol against one DLL -- so each one declared against the
    # other is reported missing:
    #
    #   ffi.error: symbol 'RtlNtStatusToDosError' not found in library 'kernel32.dll'
    #   ffi.error: symbol 'CancelIoEx' not found in library 'ntdll.dll'
    #
    # (They are not really missing; they are in the OTHER library of the pair.) eventlet
    # catches it and carries on, so the app still starts -- with only part of the patch
    # applied, which is the worst of the three possible states.
    #
    # Import ORDER cannot fix this: `import eventlet` pulls trio in by itself, so there is no
    # position early enough. Skipping greendns stops dnspython -- and therefore trio -- from
    # being imported at all. Verified: with this set, no trio module loads and monkey_patch()
    # completes silently. greendns only matters for non-blocking DNS, which this launcher
    # does not rely on.
    os.environ.setdefault("EVENTLET_NO_GREENDNS", "yes")
    try:
        import eventlet

        eventlet.monkey_patch()
    except ImportError:
        pass

# Deliberately below the patch -- see above. E402 is the linter noticing exactly that, which is
# why it is silenced here rather than "fixed" by moving them back up.
import platform              # noqa: E402
import re                    # noqa: E402
import time                  # noqa: E402
import signal                # noqa: E402
import logging               # noqa: E402
import subprocess            # noqa: E402
import importlib.util        # noqa: E402

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
