"""lab [--port 8080] [--no-sandbox]"""

from __future__ import annotations

import argparse

import uvicorn

from .app import create_app


def main() -> None:
    p = argparse.ArgumentParser(prog="lab", description="System One Playground: gateway and UI")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--no-sandbox", action="store_true", help="run local engines without the macOS network sandbox")
    p.add_argument("--open", action="store_true", help="open the playground in a browser once it is up")
    args = p.parse_args()
    url = f"http://{args.host}:{args.port}"
    print(f"System One Playground on {url}")
    if args.open:
        import threading
        import webbrowser

        threading.Timer(1.5, webbrowser.open, args=(url,)).start()
    uvicorn.run(create_app(sandbox=not args.no_sandbox), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
