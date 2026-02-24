"""
Vercel serverless entry point — wraps the Flask app for Vercel Python runtime.
"""

import sys
import os

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from dashboard.app import create_app

app = create_app()
