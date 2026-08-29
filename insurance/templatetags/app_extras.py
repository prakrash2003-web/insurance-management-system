from django import template

register = template.Library()


@register.simple_tag
def qs_replace(request, **kwargs):
    """Rebuild the current querystring with some keys overridden."""
    params = request.GET.copy()
    for key, value in kwargs.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()


@register.filter
def badge_class(value):
    """Map a status string to a CSS badge modifier."""
    return "badge--" + str(value).lower().replace(" ", "")


@register.filter
def field_type(field):
    return field.field.widget.__class__.__name__
