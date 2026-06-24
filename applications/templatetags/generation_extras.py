from django import template

from applications.services import render_structured

register = template.Library()


@register.filter
def pretty_generated(value):
    """Render JSON/Python-dict-like generated text as readable sections."""
    return render_structured(value)
