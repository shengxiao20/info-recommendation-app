"""Server-only configuration. Never embed this module in the frontend."""
import os
from pathlib import Path

from .environment import load_environment, require_environment

ROOT = Path(__file__).resolve().parent.parent
load_environment(ROOT / '.env')
SYSTEM_ONE_URL = 'https://ws-bkrg0ykeczqe4oz1.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/systemone'
DASHSCOPE_API_KEY = require_environment('DASHSCOPE_API_KEY')
RELEVANCE_THRESHOLD = 0.5
DATABASE_PATH = ROOT / 'data/articles.db'
SEED_PATH = ROOT / 'resources/articles.seed.db'
FRONTEND_PATH = ROOT / 'release/文章洞察-前端.html'
HOST = os.environ.get('ARTICLE_LENS_HOST', '127.0.0.1')
PORT = int(os.environ.get('ARTICLE_LENS_PORT', '8787'))
