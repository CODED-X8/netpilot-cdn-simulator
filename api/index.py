"""Vercel Serverless Function entrypoint for Mini CDN Routing Simulator & NetPilot.

Exposes the Flask WSGI 'app' instance for Vercel's Python runtime.
Includes WSGI path normalization middleware so that Vercel rewrites to /api/index
seamlessly route to the correct Flask endpoints and static assets.
"""

import os
import sys

# Add project root directory to sys.path so internal imports resolve cleanly
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dashboard.app import app


class VercelPathFixMiddleware:
    """WSGI middleware ensuring proper PATH_INFO routing under Vercel rewrites.

    Vercel rewrites catch-all traffic to /api/index, which populates PATH_INFO with
    '/api/index' while storing the true requested URI in HTTP_X_MATCHED_PATH or
    HTTP_X_FORWARDED_PATH. This middleware restores PATH_INFO so Flask routes and
    static assets match accurately.
    """

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        raw_path = environ.get("PATH_INFO", "")
        # Check Vercel routing headers
        matched = (
            environ.get("HTTP_X_MATCHED_PATH")
            or environ.get("HTTP_X_VERCEL_MATCHED_PATH")
            or environ.get("HTTP_X_FORWARDED_PATH")
            or environ.get("HTTP_X_ORIGINAL_URI")
        )

        if matched:
            # Strip query string from matched path if present
            clean_matched = matched.split("?")[0]
            if clean_matched:
                environ["PATH_INFO"] = clean_matched
        elif raw_path in ("/api/index", "/api/index.py", "/api", ""):
            environ["PATH_INFO"] = "/"

        return self.wsgi_app(environ, start_response)


# Wrap Flask's wsgi_app with the path normalization middleware
app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)
