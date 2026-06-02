#!/usr/bin/env python3
from __future__ import annotations

import os
import json
from functools import lru_cache
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from subprocess import run

BASE = Path('/home/oleg/.openclaw/workspace/chat_stats_dashboard')
BUILD_LOG = BASE / 'build_message_log.py'
INGEST = BASE / 'ingest_incoming_telegram.py'
GEN = BASE / 'generate_stats.py'
PORT = int(os.environ.get('CHAT_STATS_PORT', '8091'))


@lru_cache(maxsize=1)
def regenerate() -> None:
    run(['python3', str(INGEST)], cwd=str(BASE), check=False)
    run(['python3', str(BUILD_LOG)], cwd=str(BASE), check=False)
    run(['python3', str(GEN)], cwd=str(BASE), check=False)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE), **kwargs)

    def _send_json(self, payload: dict, status: int = 200):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path == '/refresh':
            regenerate.cache_clear()
            regenerate()
            return self._send_json({'ok': True})
        if path == '/stats.json':
            regenerate.cache_clear()
            regenerate()
        elif path not in ('/', '/index.html'):
            self.path = '/index.html'
        return super().do_GET()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()


if __name__ == '__main__':
    regenerate()
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
