from django import template

register = template.Library()


@register.filter
def blank_dash(value):
    """Show an em dash for an empty cell, such as a fee record with no room."""
    return "—" if value in ("", None) else value
