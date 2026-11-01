import hashlib
from functools import lru_cache

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@lru_cache(maxsize=None)
def _digest(path):
    found = finders.find(path)
    if not found:
        return ''
    with open(found, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()[:10]


@register.simple_tag
def versioned_static(path):
    """static() URL with a content hash, so assets can be cached for a long time."""
    url = static(path)
    digest = _digest(path)
    return f'{url}?v={digest}' if digest else url
