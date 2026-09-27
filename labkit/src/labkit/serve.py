"""python -m labkit.serve --engine engine_laya:load --model english --device mps --port 9101"""

from __future__ import annotations

import argparse
import os
import threading
import time

import uvicorn

from .server import EngineState, create_app, resolve_loader


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="labkit.serve")
    p.add_argument("--engine", required=True, help="module:function that loads a Predictor")
    p.add_argument("--model", required=True)
    p.add_argument("--device", default="cpu")
    p.add_argument("--threads", type=int, default=None)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--exit-with-parent", action="store_true", help="exit when the process that started this one goes away")
    args = p.parse_args(argv)
    if args.exit_with_parent:
        watch_parent(os.getppid())

    loader = resolve_loader(args.engine)
    state = EngineState(args.engine, args.model, args.device, args.threads)
    uvicorn.run(create_app(state, loader), host=args.host, port=args.port, log_level="warning", access_log=False)


def watch_parent(parent: int) -> None:
    """Exit as soon as the parent dies, even if it was SIGKILLed and never got to stop us."""

    def loop() -> None:
        while True:
            if os.getppid() != parent:
                os._exit(0)
            time.sleep(0.5)

    threading.Thread(target=loop, name="parent-watch", daemon=True).start()


if __name__ == "__main__":
    main()
