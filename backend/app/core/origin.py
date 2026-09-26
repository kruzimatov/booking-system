from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.errors import error_response

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _hostname(url: str) -> str | None:
    # Host names only: ports are not a cookie boundary, and proxies may drop the port.
    return urlsplit(url).hostname


class SameOriginMiddleware:
    """Rejects state-changing browser requests sent from another origin.

    SameSite=Lax already stops other websites, but other subdomains of the same domain
    count as "same site" and would still send the login cookie. Browsers always attach an
    Origin header to cross-origin POST, PUT, PATCH and DELETE requests, so comparing it
    with the Host header closes that gap. Requests without an Origin (curl, server-to-
    server) are not browser-initiated and are allowed.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] not in SAFE_METHODS:
            headers = Headers(scope=scope)
            origin = headers.get("origin")
            origin_host = _hostname(origin) if origin is not None else None
            own_host = _hostname("//" + headers.get("host", ""))
            # An unparseable Origin (such as "null" from a sandboxed frame) never matches.
            if origin is not None and (origin_host is None or origin_host != own_host):
                response = error_response(
                    403, "CROSS_ORIGIN_REQUEST", "Requests from other websites are not allowed."
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
