#!/usr/bin/env python3
"""
Local dev server for the promotion dashboard.

- GET  /                      → serves HTML with current data.json injected
- GET  /development_plan.html → same
- GET  /data                  → returns data.json as JSON
- POST /save  {state:{...}}   → writes data.json, runs generate_md.py

Usage:
    python3 serve.py
Then open: http://localhost:7654/
"""

import http.server, json, os, subprocess, sys

PORT    = 7654
DIR     = os.path.dirname(os.path.abspath(__file__))
HTML_FN = "development_plan.html"
DATA_FN = "data.json"


def safe_json(obj) -> str:
    """JSON string safe to embed inside a <script> tag (escapes < > &)."""
    return json.dumps(obj, ensure_ascii=False) \
               .replace("&", r"\u0026") \
               .replace("<", r"\u003c") \
               .replace(">", r"\u003e")


class Handler(http.server.SimpleHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors(); self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", f"/{HTML_FN}"):
            self._serve_dashboard()
        elif path == "/data":
            self._serve_data()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path != "/save":
            self.send_response(404); self.end_headers(); return

        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length))
        state  = body.get("state")
        if state is None:
            self._respond({"ok": False, "stderr": "Missing 'state' key"}); return

        # Write data file (use provided filename, restricted to this dir)
        filename  = os.path.basename(body.get("filename", DATA_FN))
        data_path = os.path.join(DIR, filename)
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

        # Regenerate markdown with matching filename
        result = subprocess.run(
            [sys.executable, "generate_md.py", filename],
            capture_output=True, text=True, cwd=DIR
        )
        self._respond({"ok": result.returncode == 0,
                       "stdout": result.stdout, "stderr": result.stderr})

    # ── helpers ──────────────────────────────────────────────────────────────

    def _serve_dashboard(self):
        html_path = os.path.join(DIR, HTML_FN)
        data_path = os.path.join(DIR, DATA_FN)
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        if os.path.exists(data_path):
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            tag = (f'<script id="_initial_data" type="application/json">'
                   f'{safe_json(data)}</script>')
            html = html.replace("</head>", tag + "\n</head>", 1)
        content = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_data(self):
        data_path = os.path.join(DIR, DATA_FN)
        if os.path.exists(data_path):
            with open(data_path, "rb") as f:
                content = f.read()
        else:
            content = b"null"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _respond(self, data: dict):
        payload = json.dumps(data).encode()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt, *args):
        print(f"  {args[0]} {args[1]}")


if __name__ == "__main__":
    os.chdir(DIR)
    httpd = http.server.HTTPServer(("localhost", PORT), Handler)
    print(f"✅  Dashboard server running")
    print(f"   Open → http://localhost:{PORT}/")
    print(f"   Data → {os.path.join(DIR, DATA_FN)}")
    print(f"   Ctrl-C to stop\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
