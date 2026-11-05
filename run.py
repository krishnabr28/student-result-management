"""Start the web application: python run.py"""

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "5000"))
    shown = "localhost" if host == "127.0.0.1" else host
    print(f"Student Result Management System running at http://{shown}:{port}")
    app.run(host=host, port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
