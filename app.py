"""TurnCheck: the interview screen.

    python3 app.py                 then open http://localhost:8000
    python3 app.py --port 8001

Needs Ollama running with qwen2.5:7b. Without it the screen still works:
TurnCheck asks you how to read every turn instead of guessing.
One interview at a time. Each one is saved to sessions/ so you can inspect it.
"""
import argparse
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from turncheck.controller import Interview, apply
from turncheck.readings import OllamaReader

HERE = Path(__file__).resolve().parent
PAGES = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}
TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json"}
ACTIONS = {
    "/api/start": lambda body: {"start": True},
    "/api/turn": lambda body: {"turn": str(body.get("text", ""))[:2000]},
    "/api/choose": lambda body: {"choose": body.get("option")},
    "/api/correct": lambda body: {"correct": body.get("id"), "to": body.get("to")},
}


class Session:
    """The one interview in progress, and the file it is saved to."""

    def __init__(self, script_path, reader):
        self.script_path, self.reader = script_path, reader
        self.script = json.loads(script_path.read_text())
        self.lock = threading.Lock()
        self.interview, self.steps, self.file = Interview(self.script, reader), [], None

    def act(self, action):
        with self.lock:
            if "start" in action:  # Start always begins a fresh interview
                self.interview, self.steps = Interview(self.script, self.reader), []
                self.file = HERE / "sessions" / f"{time.strftime('%Y-%m-%d-%H%M%S')}.json"
            step = apply(self.interview, action)
            self.steps.append(step)
            for entry in step["trace"]:
                print(f"  {entry['action']}  ->  {entry['edge']}  ->  {entry['did']}")
            if self.file:
                self.file.parent.mkdir(exist_ok=True)
                self.file.write_text(json.dumps({"script": self.script_path.name, "model": self.reader.model,
                                                 "steps": self.steps}, indent=1, ensure_ascii=False))
            return step["view"]


class Handler(BaseHTTPRequestHandler):
    session = None

    def do_GET(self):
        path = self.path.split("?")[0]
        trace = re.fullmatch(r"/traces/([a-z0-9-]+\.json)", path)
        if path in PAGES:
            self._file(HERE / "static" / PAGES[path])
        elif trace and (HERE / "results" / "traces" / trace.group(1)).is_file():
            self._file(HERE / "results" / "traces" / trace.group(1))
        elif path == "/api/view":
            self._send(json.dumps(self.session.interview.view()).encode(), "application/json")
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path not in ACTIONS:
            return self.send_error(404)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            return self.send_error(400)
        self._send(json.dumps(self.session.act(ACTIONS[self.path](body))).encode(), "application/json")

    def _file(self, path):
        self._send(path.read_bytes(), TYPES[path.suffix])

    def _send(self, data, kind):
        self.send_response(200)
        self.send_header("Content-Type", kind + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # keep the terminal for the turn-by-turn lines printed above
        pass


def main():
    parser = argparse.ArgumentParser(description="Run the TurnCheck interview screen.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--script", type=Path, default=HERE / "interview" / "data-engineer.json")
    args = parser.parse_args()

    reader = OllamaReader(args.model)
    Handler.session = Session(args.script, reader)

    def warm_up():
        ready = reader.warm_up()
        print(f"Model {args.model} is ready." if ready else
              "Ollama is not answering, so TurnCheck will ask you how to read every turn.")
    threading.Thread(target=warm_up, daemon=True).start()

    print(f"TurnCheck is at http://localhost:{args.port}   (Ctrl+C to stop)")
    try:
        ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
