"""SQLite persistence with per-file transactional imports."""
import json
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .validation import ValidationError, validate_article


class ArticleStore:
    def __init__(self, database_path, seed_path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        restore_seed = not self.database_path.exists()
        if not restore_seed:
            with closing(self._connect()) as database:
                restore_seed = database.execute('SELECT COUNT(*) FROM articles').fetchone()[0] == 0
        if restore_seed:
            shutil.copyfile(seed_path, self.database_path)
        with closing(self._connect()) as database, database:
            database.execute("""CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                content TEXT NOT NULL, source TEXT, published_at TEXT,
                created_at TEXT NOT NULL, filtered INTEGER NOT NULL DEFAULT 0,
                matched_tags TEXT NOT NULL DEFAULT '[]')""")
            columns = [row['name'] for row in database.execute('PRAGMA table_info(articles)')]
            if 'published_at' not in columns:
                database.execute('ALTER TABLE articles ADD COLUMN published_at TEXT')

    def _connect(self):
        database = sqlite3.connect(self.database_path)
        database.row_factory = sqlite3.Row
        return database

    def list_articles(self, query=''):
        with closing(self._connect()) as database:
            return [dict(row) for row in database.execute(
                'SELECT * FROM articles WHERE title LIKE ? ORDER BY id DESC', (f'%{query}%',)
            )]

    def import_files(self, files):
        if not isinstance(files, list):
            raise ValidationError('files 必须是文件数组')
        if any(not isinstance(file, dict) or set(file) != {'name', 'text'}
               or not isinstance(file['name'], str) or not isinstance(file['text'], str) for file in files):
            raise ValidationError('每个文件必须包含字符串 name 和 text')
        count, errors = 0, []
        for file in files:
            try:
                try:
                    data = json.loads(file['text'])
                except json.JSONDecodeError as error:
                    raise ValidationError('不是合法的 JSON 文件') from error
                records = data if isinstance(data, list) else [data]
                if not records:
                    raise ValidationError('文章数组不能为空')
                validated = [validate_article(record, f'第 {index + 1} 篇') for index, record in enumerate(records)]
                with closing(self._connect()) as database, database:
                    database.executemany('''INSERT INTO articles
                        (title, content, source, published_at, created_at, filtered, matched_tags)
                        VALUES (?, ?, ?, ?, ?, 0, ?)''', [
                        (article['title'], article['content'], article.get('source', file['name']),
                         article.get('publishedAt'), datetime.now(timezone.utc).isoformat(),
                         json.dumps(article.get('tags', []), ensure_ascii=False)) for article in validated
                    ])
                count += len(validated)
            except ValidationError as error:
                errors.append(f'{file["name"]}：{error}')
        return {'importedCount': count, 'errors': errors}
