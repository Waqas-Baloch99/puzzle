from django import template

register = template.Library()

@register.filter
def lookup(dictionary, key):
    return dictionary.get(key)

@register.filter
def split(value, delimiter=','):
    """Split a string into a list using the given delimiter."""
    return [x.strip() for x in value.split(delimiter)]

@register.filter
def trim(value):
    """Remove leading and trailing whitespace."""
    return value.strip() if value else value
