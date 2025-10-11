from waitress import serve
from app import app

if __name__ == "__main__":
    # Bind to loopback so the app is only reachable via Nginx (HTTPS)
    # Increase threads to improve tolerance to slow upstream calls
    serve(app, host="127.0.0.1", port=9876, threads=16)
