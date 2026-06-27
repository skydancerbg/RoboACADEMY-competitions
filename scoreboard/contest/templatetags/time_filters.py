from django import template

register = template.Library()


@register.filter
def format_ms(value):
    """Format an integer millisecond value as M:SS.mmm (e.g. 75432 → 1:15.432)."""
    if value is None:
        return '—'
    value = int(value)
    ms      = value % 1000
    seconds = (value // 1000) % 60
    minutes = value // 60000
    return f'{minutes}:{seconds:02d}.{ms:03d}'
