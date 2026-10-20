"""Vercel Serverless Function entrypoint for Mini CDN Routing Simulator & NetPilot.

Exposes the Flask WSGI 'app' instance for Vercel's Python runtime.
Includes WSGI path normalization middleware so that Vercel rewrites to /api/index
seamlessly route to the correct Flask endpoints and static assets.
"""

import os
import sys
import urllib.parse

# Add project root directory to sys.path so internal imports resolve cleanly
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dashboard.app import app


class VercelPathFixMiddleware:
    """WSGI middleware ensuring proper PATH_INFO routing under Vercel rewrites.

    Vercel rewrites catch-all traffic to /api/index?__path=$1. This middleware extracts
    the true requested path from the query string or system headers and sets PATH_INFO
    accordingly, cleaning the query string so Flask endpoints and static files work seamlessly.
    """

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        query_string = environ.get("QUERY_STRING", "")
        if "__path=" in query_string:
            params = urllib.parse.parse_qs(query_string, keep_blank_values=True)
            if "__path" in params and params["__path"] and params["__path"][0]:
                target_path = "/" + params["__path"][0].lstrip("/")
                environ["PATH_INFO"] = target_path
            else:
                environ["PATH_INFO"] = "/"

            # Clean __path out of QUERY_STRING
            if "__path" in params:
                del params["__path"]
            pairs = []
            for k, vlist in params.items():
                for v in vlist:
                    pairs.append(f"{urllib.parse.quote(k)}={urllib.parse.quote(v)}")
            environ["QUERY_STRING"] = "&".join(pairs)
        else:
            raw_path = environ.get("PATH_INFO", "")
            matched = (
                environ.get("HTTP_X_MATCHED_PATH")
                or environ.get("HTTP_X_VERCEL_MATCHED_PATH")
                or environ.get("HTTP_X_FORWARDED_PATH")
                or environ.get("HTTP_X_ORIGINAL_URI")
            )
            if matched:
                clean_matched = matched.split("?")[0]
                if clean_matched:
                    environ["PATH_INFO"] = clean_matched
            elif raw_path in ("/api/index", "/api/index.py", "/api", ""):
                environ["PATH_INFO"] = "/"

        return self.wsgi_app(environ, start_response)


# Wrap Flask's wsgi_app with the path normalization middleware
app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)
