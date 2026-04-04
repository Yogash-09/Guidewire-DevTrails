"""
Thin shim — kept for convenience.
All logic lives in app.py.
Admin dashboard is served from the same app:
  http://localhost:5000/admin/login
"""
from app import app

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
