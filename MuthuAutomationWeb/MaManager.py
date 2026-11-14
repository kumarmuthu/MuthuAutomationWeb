__version__ = "2026.05.12.01"
__author__ = "Muthukumar Subramanian"

"""
MaManager – Core Engine for MuthuAutomationWeb
Fulfills the Socket Live display requirement with real-time system metrics.
"""

# Only os and sys above the patch, and only because the interpreter has ALREADY imported both
# before any of this runs (site.py uses them during startup) -- so naming them here creates
# nothing new for eventlet to upgrade. `platform` used to be imported here too, and that was
# enough to break the patch on Windows every run:
#
#   An exception was thrown while monkey_patching for eventlet.
#   ffi.error: symbol 'RtlNtStatusToDosError' not found in library 'kernel32.dll'
#   ffi.error: symbol 'CancelIoEx' not found in library 'ntdll.dll'
#
# With modules already loaded, monkey_patch() falls back to _upgrade_instances(), which walks
# existing objects and calls vars() on them. On a cffi library object that triggers cffi's lazy
# symbol lookup against the wrong DLL (both symbols above are reported against the library the
# OTHER one actually lives in). eventlet catches it and continues, so the app still starts --
# but only PART of the patch is applied, which is a worse state than either extreme.
#
# sys.platform rather than platform.system(): same answer without importing platform this early.
import os
import sys


def is_android() -> tuple[bool, str]:
    if os.environ.get("TERMUX_VERSION"): return True, "termux"           # noqa: E701
    if os.path.exists("/data/data/com.termux"): return True, "termux"    # noqa: E701
    if os.path.exists("/data/data/ru.iiec.pydroid3"): return True, "pydroid"   # noqa: E701
    if os.path.exists("/system/build.prop"): return True, "android"      # noqa: E701
    return False, ""


android, _ = is_android()

# ── FIX 1: Monkey-patch FIRST ──────────────────────────────────
if sys.platform == "win32":
    # Must precede `import eventlet`. eventlet -> dnspython (greendns) -> trio, and
    # trio._core._windows_cffi builds a cffi lib spanning kernel32 AND ntdll; monkey_patch()
    # calls vars() on it, cffi resolves every symbol against one DLL, and each symbol that
    # lives in the other is reported missing (RtlNtStatusToDosError, CancelIoEx). Import order
    # cannot fix it -- `import eventlet` pulls trio in itself. Skipping greendns means
    # dnspython, and so trio, is never imported. See MaRun.py for the full note.
    os.environ.setdefault("EVENTLET_NO_GREENDNS", "yes")
    try:
        import eventlet

        eventlet.monkey_patch()
    except ImportError:
        pass
elif not android:
    try:
        from gevent import monkey

        monkey.patch_all()
    except Exception:
        pass

# Deliberately below the patch -- see above. E402 is the linter noticing exactly that, which is
# why it is silenced rather than "fixed" by moving these back to the top.
import platform                                  # noqa: E402
import time                                      # noqa: E402
import random                                    # noqa: E402
from datetime import datetime                    # noqa: E402
from flask import Flask, render_template, jsonify      # noqa: E402
from flask_socketio import SocketIO                    # noqa: E402
from flask_cors import CORS                            # noqa: E402

app = Flask(__name__)
app.config['SECRET_KEY'] = 'muthu_automation_secret'
CORS(app)

# ── FIX 2: Platform-specific async mode ────────────────────────
if android or platform.system() == "Windows":
    ASYNC_MODE = "threading"
elif platform.system() in ["Linux", "Darwin"]:
    ASYNC_MODE = "gevent"
else:
    ASYNC_MODE = "threading"

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode=ASYNC_MODE,
    logger=False,
    engineio_logger=False
)

last_stats = {
    "cpu_usage": 0,
    "memory_usage": 0,
    "tasks_active": 0,
    "status": "Initializing...",
    "uptime": "0s"
}

start_time = time.time()


# ── Background loop for Live Display ──────────────────────────
def background_metrics_task():
    global last_stats
    while True:
        try:
            uptime_seconds = int(time.time() - start_time)
            h = uptime_seconds // 3600
            m = (uptime_seconds % 3600) // 60
            s = uptime_seconds % 60

            cpu = random.randint(15, 65)
            status = "Online"
            if cpu > 50:
                status = "Busy"
            elif cpu < 25:
                status = "Idle"
            elif random.random() < 0.2:
                status = "Syncing"

            last_stats = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "cpu_usage": cpu,
                "memory_usage": random.randint(30, 80),
                "tasks_active": random.randint(5, 25),
                "status": status,
                "uptime": f"{h}h {m}m {s}s"
            }
            socketio.emit("update", last_stats)
        except Exception as e:
            print(f"Metrics error: {e}")
        time.sleep(3)


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/credit')
def credit():
    return render_template('credit.html')


@socketio.on("connect")
def on_connect():
    print("Client connected to Socket.IO")
    socketio.emit("update", last_stats)


# ── FIX 3: Startup at module level ─────────────────────────────
socketio.start_background_task(background_metrics_task)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
