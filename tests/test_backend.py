import json
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from backend import config
from backend.environment import load_environment, require_environment
from backend.storage import ArticleStore
from backend.systemone import SystemOneClient, SystemOneError
from tests.serve_backend_fixture import start_servers


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / 'articles.db'
        self.server, self.upstream = start_servers(self.database)
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.upstream.shutdown()
        self.server.server_close()
        self.upstream.server_close()
        self.temp.cleanup()

    def _request(self, path, body=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        request = Request(self.base + path, data=data, headers={'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=15) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_frontend_is_html_without_secrets(self):
        with urlopen(self.base) as response:
            html = response.read().decode()
        self.assertIn('/api/articles', html)
        self.assertNotIn(config.DASHSCOPE_API_KEY, html)
        self.assertNotIn(config.SYSTEM_ONE_URL, html)
        self.assertNotIn('test-server-key', html)
        self.assertNotIn('article-data', html)
        for relative in ['backend/config.py', '.env.example']:
            self.assertNotIn(config.DASHSCOPE_API_KEY, (config.ROOT / relative).read_text(encoding='utf-8'))

    def test_seed_search_and_sql_parameterization(self):
        status, articles = self._request('/api/articles')
        self.assertEqual(status, 200)
        self.assertEqual(len(articles), 100)
        self.assertGreater(articles[0]['id'], articles[-1]['id'])
        from urllib.parse import quote
        _, matches = self._request('/api/articles?query=' + quote('人工智能'))
        self.assertTrue(matches)
        self.assertTrue(all('人工智能' in article['title'] for article in matches))
        self.assertEqual(self._request('/api/articles?query=%25')[1], articles)
        self.assertEqual(self._request('/api/articles?query=' + quote("' OR 1=1 --"))[1], [])

    def test_import_is_atomic_per_file_and_persistent(self):
        files = [
            {'name': 'invalid.json', 'text': json.dumps([{'title': '不能部分导入'}, {'title': 'extra', 'bad': 1}])},
            {'name': 'valid.json', 'text': json.dumps({'title': ' 完整文章 ', 'content': ' 正文 ', 'tags': ['AI'],
                                                     'source': 'https://example.com', 'publishedAt': '2026-01-01T00:00:00Z'})},
            {'name': 'empty.json', 'text': '[]'},
            {'name': 'malformed.json', 'text': '{'},
        ]
        status, result = self._request('/api/articles/import', {'files': files})
        self.assertEqual(status, 200)
        self.assertEqual(result['importedCount'], 1)
        self.assertEqual(len(result['errors']), 3)
        restored = ArticleStore(self.database, config.SEED_PATH).list_articles()
        self.assertEqual(len(restored), 101)
        self.assertEqual(restored[0]['title'], '完整文章')
        self.assertEqual(restored[0]['content'], '正文')
        self.assertEqual(restored[0]['matched_tags'], '["AI"]')

    def test_invalid_import_and_filter_requests(self):
        for path, body in [('/api/articles/import', {'files': {}}),
                           ('/api/articles/import', {'files': [{'name': 'x'}]}),
                           ('/api/articles/filter', {'tags': []}),
                           ('/api/articles/filter', {'tags': ['AI', 'AI']}),
                           ('/api/articles/filter', {'tags': [None]}),
                           ('/api/articles/filter', {'tags': ['AI'], 'extra': True})]:
            self.assertEqual(self._request(path, body)[0], 400)
        self.assertEqual(self._request('/api/articles/import', raw=b'{')[0], 400)
        self.assertEqual(self._request('/unknown')[0], 404)
        self.assertEqual(len(self.upstream.calls), 0)

    def test_systemone_real_http_contract_and_library_isolation(self):
        before = self.server.store.list_articles()
        status, matched = self._request('/api/articles/filter', {'tags': ['AI', '经济']})
        self.assertEqual(status, 200)
        self.assertEqual(len(self.upstream.calls), 100)
        self.assertEqual(len(matched), 2)
        self.assertEqual(json.loads(matched[0]['matched_tags']), ['AI'])
        self.assertEqual(json.loads(matched[1]['matched_tags']), ['经济'])
        self.assertEqual(self.server.store.list_articles(), before)
        for call in self.upstream.calls:
            self.assertEqual(call['authorization'], 'Bearer test-server-key')
            body = call['body']
            self.assertEqual(body['model'], 'decision-model-preview')
            self.assertEqual(set(body['state']['article']), {'title', 'content'})
            self.assertEqual(set(body['questions']), {'tag_0', 'tag_1'})
            self.assertEqual(body['questions']['tag_0']['type'], 'noul')

    def test_upstream_errors_are_explicit(self):
        for mode, message in [('http', '401'), ('invalid', '返回格式错误'), ('invalid-json', '合法 JSON')]:
            self.upstream.mode = mode
            status, body = self._request('/api/articles/filter', {'tags': ['AI']})
            self.assertEqual(status, 502)
            self.assertIn(message, body['error'])
            self.assertNotIn(config.DASHSCOPE_API_KEY, body['error'])
        unavailable = SystemOneClient('http://127.0.0.1:1/systemone', 'test-key', 0.5)
        with self.assertRaisesRegex(SystemOneError, '网络请求失败'):
            unavailable.filter_articles(self.server.store.list_articles()[:1], ['AI'])


class EnvironmentTests(unittest.TestCase):
    def test_load_file_and_exported_variable_precedence(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'EXPORTED': 'shell-value'}, clear=True):
            path = Path(directory) / '.env'
            path.write_text('# comment\n\nDASHSCOPE_API_KEY="test-only-key"\nEXPORTED=file-value\nSINGLE=\'quoted\'\n', encoding='utf-8')
            load_environment(path)
            self.assertEqual(require_environment('DASHSCOPE_API_KEY'), 'test-only-key')
            self.assertEqual(os.environ['EXPORTED'], 'shell-value')
            self.assertEqual(os.environ['SINGLE'], 'quoted')

    def test_missing_file_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                load_environment(Path(directory) / '.env')

    def test_invalid_file_is_rejected_without_partial_loading(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            path = Path(directory) / '.env'
            for invalid in ['no-equals', 'BAD NAME=value', 'VALID=duplicate', 'OTHER="unclosed']:
                path.write_text('VALID=first\n' + invalid, encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_environment(path)
                self.assertNotIn('VALID', os.environ)

    def test_missing_or_empty_key_raises_without_a_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, '缺少 DASHSCOPE_API_KEY'):
                require_environment('DASHSCOPE_API_KEY')
            for value in ['', '   ']:
                os.environ['DASHSCOPE_API_KEY'] = value
                with self.assertRaisesRegex(ValueError, '不能为空'):
                    require_environment('DASHSCOPE_API_KEY')


if __name__ == '__main__':
    unittest.main()
