from django.core.paginator import Paginator
from django.utils.http import url_has_allowed_host_and_scheme


def is_modal_request(request):
    """Return True when a request is asking for a modal form partial."""
    return (
        request.GET.get('modal') == '1'
        or request.headers.get('X-Requested-With') == 'fetch'
    )


def safe_next_url(request, candidate):
    """Return a safe same-host redirect target, or None."""
    if not candidate:
        return None
    if url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return None


def paginate(request, queryset, per_page):
    """Return ``(page_obj, query_string)`` for a paginated list view.

    ``query_string`` carries the current filters (minus ``page``) so the
    pagination links preserve them.
    """
    page_obj = Paginator(queryset, per_page).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return page_obj, params.urlencode()
