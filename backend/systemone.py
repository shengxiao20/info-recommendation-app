"""Real SystemOne filtering, executed only on the server."""
import json
import math
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .validation import validate_filter_tags


class SystemOneError(RuntimeError):
    pass


class SystemOneClient:
    def __init__(self, url, api_key, threshold):
        self.url = url
        self.api_key = api_key
        self.threshold = threshold

    def filter_articles(self, articles, tags):
        validate_filter_tags(tags)
        questions = {f'tag_{index}': {
            'type': 'noul',
            'instructions': f'文章是否与用户兴趣标签“{tag}”相关？仅当文章的主要内容或重要内容与该标签直接相关时判定为是。',
            'criteria': {'true': '文章与该兴趣标签相关', 'false': '文章与该兴趣标签不相关'},
        } for index, tag in enumerate(tags)}
        matched = []
        for article in articles:
            result = self._request({
                'model': 'decision-model-preview',
                'state': {'article': {'title': article['title'], 'content': article['content']}},
                'questions': questions,
            })
            matched_tags = []
            for index, tag in enumerate(tags):
                answer = result.get('answers', {}).get(f'tag_{index}')
                if (not isinstance(answer, dict) or answer.get('type') != 'noul'
                        or type(answer.get('noul')) not in (int, float) or not math.isfinite(answer['noul'])):
                    raise SystemOneError(f'SystemOne 返回格式错误：缺少 tag_{index} 的有效 noul 评分')
                if answer['noul'] >= self.threshold:
                    matched_tags.append(tag)
            if matched_tags:
                matched.append({**article, 'matched_tags': json.dumps(matched_tags, ensure_ascii=False)})
        return matched

    def _request(self, payload):
        request = Request(self.url, method='POST', data=json.dumps(payload).encode('utf-8'), headers={
            'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}',
        })
        try:
            with urlopen(request, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
        except HTTPError as error:
            detail = error.read().decode('utf-8', errors='replace').replace(self.api_key, '[REDACTED]')
            raise SystemOneError(f'SystemOne 决策模型请求失败：{error.code} {detail}') from error
        except (URLError, TimeoutError) as error:
            raise SystemOneError(f'SystemOne 网络请求失败：{error}') from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise SystemOneError('SystemOne 返回的内容不是合法 JSON') from error
        if not isinstance(result, dict) or not isinstance(result.get('answers'), dict):
            raise SystemOneError('SystemOne 返回格式错误：缺少 answers 对象')
        return result
