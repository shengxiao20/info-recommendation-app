"""Local upstream fixture. It never calls the real paid SystemOne endpoint."""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from backend import config
from backend.server import ArticleServer
from backend.storage import ArticleStore
from backend.systemone import SystemOneClient


class UpstreamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlsplit(self.path).query)
        if 'mode' in query:
            self.server.mode = query['mode'][0]
            self.server.calls = []
        self._send(200, {'calls': len(self.server.calls)})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.calls.append({'body': body, 'authorization': self.headers.get('Authorization')})
        mode = self.server.mode
        if mode == 'http':
            self._send(401, {'error': 'test unauthorized'})
        elif mode == 'invalid':
            self._send(200, {'answers': {}})
        elif mode == 'invalid-json':
            self._send(200, 'not-json')
        else:
            count = len(self.server.calls)
            answers = {key: {'type': 'noul', 'noul': 0.49} for key in body['questions']}
            if count == 1:
                answers['tag_0']['noul'] = 0.5
            if count == 2 and 'tag_1' in answers:
                answers['tag_1']['noul'] = 0.8
            self._send(200, {'answers': answers})

    def _send(self, status, value):
        body = value.encode() if isinstance(value, str) else json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def start_servers(database_path):
    upstream = ThreadingHTTPServer(('127.0.0.1', 0), UpstreamHandler)
    upstream.mode = 'success'
    upstream.calls = []
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    store = ArticleStore(database_path, config.SEED_PATH)
    client = SystemOneClient(f'http://127.0.0.1:{upstream.server_port}/systemone', 'test-server-key', 0.5)
    server = ArticleServer(('127.0.0.1', 0), store, client, config.FRONTEND_PATH)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, upstream


if __name__ == '__main__':
    server, upstream = start_servers(Path(sys.argv[1]))
    print(json.dumps({'base': f'http://127.0.0.1:{server.server_port}',
                      'upstream': f'http://127.0.0.1:{upstream.server_port}'}), flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        server.shutdown()
        upstream.shutdown()
        server.server_close()
        upstream.server_close()
