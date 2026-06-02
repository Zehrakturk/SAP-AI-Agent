"""
run.py — Start the SAP AI Copilot Admin Portal.

Usage:
    python run.py

Then open → http://localhost:3000

Demo credentials:
    admin        / admin123
    a.mueller    / proc123
    r.kaya       / fin123
"""
import sys
import os
from dotenv import load_dotenv
load_dotenv()

# Make sure Python looks in THIS folder first for the 'app' package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

# app = create_app()

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  SAP AI Copilot — Admin Portal")
    print("  http://localhost:3000")
    print("=" * 50)
    print("  Demo login:  admin / admin123")
    print("=" * 50 + "\n")
    # from app.services.sap_fetcher import fetch_and_store
    # fetch_and_store()
    create_app().run(host="0.0.0.0", port=3000, debug=True)