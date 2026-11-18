"""
Minimal CORS so the Flutter WEB admin (another origin) can call the API.

settings:
  CORS_ALLOW_ALL       True  -> any origin (default while DEBUG)
  CORS_ALLOWED_ORIGINS ["https://admin.example.com", ...] otherwise
The API uses a Bearer token (no cookies) so credentials are not needed.
"""
from django.conf import settings
from django.http import HttpResponse

ALLOW_HEADERS = "authorization, content-type, accept, x-requested-with"
ALLOW_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"


def _origin_allowed(origin: str) -> bool:
    if not origin:
        return False
    if getattr(settings, "CORS_ALLOW_ALL", False):
        return True
    return origin in getattr(settings, "CORS_ALLOWED_ORIGINS", [])


class SimpleCorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin", "")
        is_preflight = request.method == "OPTIONS" and "Access-Control-Request-Method" in request.headers

        response = HttpResponse(status=204) if is_preflight else self.get_response(request)

        if _origin_allowed(origin):
            response["Access-Control-Allow-Origin"] = origin
            response["Vary"] = "Origin"
            # allow exactly the headers the browser asks for (the app sends e.g. "prefer")
            requested = request.headers.get("Access-Control-Request-Headers", "")
            response["Access-Control-Allow-Headers"] = f"{ALLOW_HEADERS}, {requested}" if requested else ALLOW_HEADERS
            response["Access-Control-Allow-Methods"] = ALLOW_METHODS
            response["Access-Control-Max-Age"] = "86400"
        return response
