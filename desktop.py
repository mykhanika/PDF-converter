"""PDF Toolkit desktop launcher: runs the local server inside a native window."""
import os, sys, time, socket, shutil, threading
from pathlib import Path
import webview

BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent

# Help the app find Tesseract and LibreOffice without the user editing PATH.
extra = [BASE / "tesseract", r"C:\Program Files\Tesseract-OCR", r"C:\Program Files\LibreOffice\program",
         r"C:\Program Files (x86)\LibreOffice\program", "/Applications/LibreOffice.app/Contents/MacOS",
         "/opt/homebrew/bin", "/usr/local/bin"]
os.environ["PATH"] = os.pathsep.join([str(p) for p in extra if Path(p).exists()] + [os.environ.get("PATH", "")])
if (BASE / "tesseract" / "tessdata").exists():  # optional bundled Tesseract
    os.environ["TESSDATA_PREFIX"] = str(BASE / "tesseract" / "tessdata")

import app as toolkit  # noqa: E402  (after PATH is prepared)

# "Open with PDF Toolkit": Windows passes the file path as an argument.
FILES = [os.path.abspath(a) for a in sys.argv[1:] if a.lower().endswith(".pdf") and os.path.isfile(a)]
if FILES: toolkit.STARTUP.append(FILES[0])
for extra_file in FILES[1:]:  # several files selected: one window each
    import subprocess
    subprocess.Popen([sys.executable, extra_file] if getattr(sys, "frozen", False) else [sys.executable, __file__, extra_file])

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]

def main():
    port = free_port()
    threading.Thread(target=lambda: toolkit.app.run("127.0.0.1", port, threaded=True, use_reloader=False),
                     daemon=True).start()
    for _ in range(100):  # wait until the server answers
        try: socket.create_connection(("127.0.0.1", port), 0.2).close(); break
        except OSError: time.sleep(0.1)
    try: webview.settings["ALLOW_DOWNLOADS"] = True  # shows a native Save dialog
    except Exception: pass
    webview.create_window("PDF Toolkit", f"http://127.0.0.1:{port}", width=1100, height=820, min_size=(760, 560))
    webview.start()
    shutil.rmtree(toolkit.WORK, ignore_errors=True)

if __name__ == "__main__":
    main()
