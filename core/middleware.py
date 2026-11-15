"""Request instrumentation used while tuning performance.

Only enabled when ``SERVER_TIMING=True`` so it never runs by default. The
``Server-Timing`` response header reports Database time and query count:

    db;dur=12.4;desc="7 queries"

Read it with ``curl -sI <url>`` or in the browser devtools network panel.
"""

from django.db import connection
from django.test.utils import CaptureQueriesContext


class ServerTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with CaptureQueriesContext(connection) as captured:
            response = self.get_response(request)

        queries = captured.captured_queries
        db_ms = sum(float(query.get('time') or 0) for query in queries) * 1000
        response['Server-Timing'] = (
            f'db;dur={db_ms:.1f};desc="{len(queries)} queries"'
        )
        return response
