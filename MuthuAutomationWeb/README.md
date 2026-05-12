# MuthuAutomationWeb

A robust Flask/SocketIO demo application designed to run seamlessly on the **MuthuFlaskAPK** Android runner. This site features automated lifecycle management and platform-aware execution.

## 📁 File Structure

```text
MuthuAutomationWeb/
├── MaManager.py          # Core Flask application & Routes
├── MaRun.py              # Platform-aware launcher & Auto-installer
├── requirements.txt      # Python dependencies
├── README.md             # Project documentation
└── templates/            # HTML Templates
    ├── home.html         # Landing Page
    ├── about.html        # About Page
    ├── login.html        # Demo Login Page
    └── credit.html       # Credits Page
```

## 🚀 Deployment on Android

1. **Compress**: Select all files in this folder and create a `.zip` archive.
2. **Upload**: Use the "Upload ZIP" feature in the **MuthuFlaskAPK** app.
3. **Configure**: Set the `Entry Module` to `MaRun`.
4. **Launch**: The app will automatically install dependencies and start the server on port 5000.

## 🛠 Features

- **Live Dashboard**: Real-time system monitoring (CPU, Memory, Tasks) using Socket.IO.
- **Dynamic Status**: Intelligent status reporting (Online, Busy, Idle, Syncing) based on server load.
- **Modern UI**: Fully responsive, mobile-first design built with Tailwind CSS.
- **Platform Detection**: Automatically adapts to Windows, Linux, macOS, Termux, or Pydroid.
- **Auto-Dependency Installation**: Reads `requirements.txt` and installs missing packages on first boot.
- **Port Management**: Attempts to free port 5000 if it's already in use.
- **SocketIO Support**: High-performance real-time communication using `eventlet` or `gevent`.

---
**Author:** Muthukumar Subramanian
**Version:** 2026.05.12.01
