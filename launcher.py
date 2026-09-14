import threading
from app import main as collector_main
from dashboard import serve

if __name__ == "__main__":
    threading.Thread(target=collector_main, daemon=True).start()
    serve()