"""Netlify Serverless Function entrypoint for Mini CDN Routing Simulator & NetPilot.

Adapts the Flask WSGI application to Netlify Functions / AWS Lambda event format.
"""

import os
import sys

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import serverless_wsgi
from dashboard.app import app


def handler(event, context):
    """Handle incoming Netlify serverless invocation."""
    return serverless_wsgi.handle_request(app, event, context)
