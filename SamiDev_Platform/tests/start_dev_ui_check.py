"""Prove the launcher rejects a mixed folder and stale HTTP content."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import start_dev

manifest = start_dev.local_build()
with tempfile.TemporaryDirectory() as folder:
    copied = Path(folder)
    for rel in ["platform/build.json", *manifest["files"]]:
        target = copied / "game" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "game" / rel, target)
    (copied / "game/platform/index.html").write_text("<html>Old interface</html>")
    start_dev.ROOT = copied
    try:
        start_dev.local_build()
        raise AssertionError("Mixed local UI was accepted")
    except RuntimeError as error:
        assert "platform/index.html" in str(error), error
    finally:
        start_dev.ROOT = ROOT


class StaleServer(BaseHTTPRequestHandler):
    def do_GET(self):
        data = json.dumps({"ok": True, **manifest}).encode() if self.path == "/api/build" else b"<html>Old UI</html>"
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


with ThreadingHTTPServer(("127.0.0.1", 0), StaleServer) as server:
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        start_dev.verify_served_ui(f"http://127.0.0.1:{server.server_port}", manifest)
        raise AssertionError("Stale HTTP UI was accepted despite correct build endpoint")
    except RuntimeError as error:
        assert "platform/index.html" in str(error), error
    finally:
        server.shutdown()
        worker.join()
print(json.dumps({"ok": True, "mixedFolderRejected": True, "staleHttpUiRejected": True}))
