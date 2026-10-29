"""HTTP transport. Run with: python3 -m backend.server."""
import json
import traceback
from functools import wraps
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from . import config
from .storage import ArticleStore
from .systemone import SystemOneClient, SystemOneError
from .validation import ValidationError

ROUTES = {}


def _route(method, path):
    def decorate(function):
        ROUTES[(method, path)] = function
        return function
    return decorate


def _json_endpoint(function):
    @wraps(function)
    def handle(handler, query):
        try:
            handler._send_json(200, function(handler, query))
        except (ValidationError, json.JSONDecodeError) as error:
            handler._send_json(400, {'error': str(error)})
        except SystemOneError as error:
            handler._send_json(502, {'error': str(error)})
        except Exception:
            traceback.print_exc()
            handler._send_json(500, {'error': '后端执行失败，请查看服务端错误日志'})
    return handle


class ArticleServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, store, systemone, frontend_path):
        self.store = store
        self.systemone = systemone
        self.frontend = frontend_path.read_bytes()
        super().__init__(address, ArticleHandler)


class ArticleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    def _dispatch(self):
        url = urlsplit(self.path)
        endpoint = ROUTES.get((self.command, url.path))
        if endpoint is None:
            self._send_json(404, {'error': '接口不存在'})
            return
        endpoint(self, parse_qs(url.query, keep_blank_values=True))

    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status, data):
        self._send(status, json.dumps(data, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')

    def _read_json(self):
        if self.headers.get_content_type() != 'application/json':
            raise ValidationError('请求 Content-Type 必须是 application/json')
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError as error:
            raise ValidationError('Content-Length 必须是整数') from error
        if length <= 0:
            raise ValidationError('请求体不能为空')
        try:
            body = json.loads(self.rfile.read(length).decode('utf-8'))
        except UnicodeDecodeError as error:
            raise ValidationError('请求体必须使用 UTF-8 编码') from error
        if not isinstance(body, dict):
            raise ValidationError('请求体必须是 JSON 对象')
        return body

    @_route('GET', '/')
    def frontend(self, query):
        self._send(200, self.server.frontend, 'text/html; charset=utf-8')

    @_route('GET', '/api/articles')
    @_json_endpoint
    def list_articles(self, query):
        return self.server.store.list_articles(query.get('query', [''])[0])

    @_route('POST', '/api/articles/import')
    @_json_endpoint
    def import_articles(self, query):
        body = self._read_json()
        if set(body) != {'files'}:
            raise ValidationError('导入请求只允许 files 字段')
        return self.server.store.import_files(body['files'])

    @_route('POST', '/api/articles/filter')
    @_json_endpoint
    def filter_articles(self, query):
        body = self._read_json()
        if set(body) != {'tags'}:
            raise ValidationError('筛选请求只允许 tags 字段')
        return self.server.systemone.filter_articles(self.server.store.list_articles(), body['tags'])


def main():
    store = ArticleStore(config.DATABASE_PATH, config.SEED_PATH)
    systemone = SystemOneClient(config.SYSTEM_ONE_URL, config.DASHSCOPE_API_KEY, config.RELEVANCE_THRESHOLD)
    with ArticleServer((config.HOST, config.PORT), store, systemone, config.FRONTEND_PATH) as server:
        print(f'Article Lens: http://{config.HOST}:{server.server_port}', flush=True)
        print(f'SQLite: {config.DATABASE_PATH}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print('\nServer stopped.', flush=True)


if __name__ == '__main__':
    main()
