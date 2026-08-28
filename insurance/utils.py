from django.core.paginator import Paginator


def paginate(request, queryset, per_page=10):
    """Return a page object for ``queryset`` using the ``?page=`` query param."""
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get("page"))


def querystring(request, **overrides):
    """Current querystring with some params replaced - handy for pagination links."""
    params = request.GET.copy()
    for key, value in overrides.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()
