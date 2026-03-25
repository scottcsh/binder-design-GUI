from pathlib import Path
import socket
import uvicorn

HOST = "0.0.0.0"
PORT = 65022


def get_local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        sock.close()


if __name__ == "__main__":
    local_ip = get_local_ip()

    print()
    print("=" * 64)
    print(f"Local access  : http://127.0.0.1:{PORT}")
    print(f"Network access: http://{local_ip}:{PORT}")
    print("=" * 64)
    print()

    uvicorn.run("app.web:app", host=HOST, port=PORT, reload=False)
