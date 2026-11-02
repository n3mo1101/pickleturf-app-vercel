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
