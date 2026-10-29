"""Article import validation, shared by all HTTP import requests."""
from datetime import datetime
from urllib.parse import urlsplit


class ValidationError(ValueError):
    pass


def validate_article(value, label):
    if not isinstance(value, dict):
        raise ValidationError(f'{label}：必须是文章对象')
    extra = set(value) - {'title', 'content', 'source', 'publishedAt', 'tags'}
    if extra:
        raise ValidationError(f'{label}：不允许的字段 {"、".join(sorted(extra))}')
    title = value.get('title')
    if not isinstance(title, str) or not title.strip() or len(title) > 500:
        raise ValidationError(f'{label}：title 必须是 1 至 500 个字符的字符串')
    if 'content' in value and not isinstance(value['content'], str):
        raise ValidationError(f'{label}：content 必须是字符串')
    if 'source' in value:
        source = value['source']
        if not isinstance(source, str):
            raise ValidationError(f'{label}：source 必须是合法 URL')
        try:
            parsed = urlsplit(source)
        except ValueError as error:
            raise ValidationError(f'{label}：source 必须是合法 URL') from error
        if not parsed.scheme or (parsed.scheme in ('http', 'https') and not parsed.netloc):
            raise ValidationError(f'{label}：source 必须是合法 URL')
    if 'publishedAt' in value:
        published = value['publishedAt']
        if not isinstance(published, str):
            raise ValidationError(f'{label}：publishedAt 必须是 ISO 8601 日期时间')
        try:
            datetime.fromisoformat(published.replace('Z', '+00:00'))
        except ValueError as error:
            raise ValidationError(f'{label}：publishedAt 必须是 ISO 8601 日期时间') from error
    if 'tags' in value:
        tags = value['tags']
        if (not isinstance(tags, list) or len(tags) > 30
                or any(not isinstance(tag, str) or not tag.strip() or len(tag) > 100 for tag in tags)
                or len(set(tags)) != len(tags)):
            raise ValidationError(f'{label}：tags 必须是最多 30 个互不重复的非空字符串')
    return {**value, 'title': title.strip(), 'content': value.get('content', '').strip()}


def validate_filter_tags(tags):
    if (not isinstance(tags, list) or not tags
            or any(not isinstance(tag, str) or not tag.strip() for tag in tags)
            or len(set(tags)) != len(tags)):
        raise ValidationError('请提供至少一个互不重复的非空兴趣标签')
    return tags
