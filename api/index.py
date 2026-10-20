"""Vercel Serverless Function entrypoint for Mini CDN Routing Simulator & NetPilot.

Exposes the Flask WSGI 'app' instance for Vercel's Python runtime.
"""

import os
import sys

# Add project root directory to sys.path so internal imports resolve cleanly
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dashboard.app import app

# Vercel's Python Serverless Runtime requires the WSGI app instance named 'app'
# This is exported here for the serverless handler
