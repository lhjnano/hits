"""HITS web server entry point.

Usage:
    python -m hits_core.main [--port PORT] [--dev]
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="HITS Web Server")
    parser.add_argument("--port", type=int, default=8765, help="Server port (default: 8765)")
    parser.add_argument("--dev", action="store_true", help="Development mode")
    args = parser.parse_args()

    import uvicorn
    from hits_core.api.server import APIServer

    server = APIServer(port=args.port, dev_mode=args.dev)
    app = server.create_app()

    print(f"HITS Web Server starting on http://127.0.0.1:{args.port}")
    if args.dev:
        print("Development mode: CSP relaxed, CORS enabled for Vite")

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=args.port,
        log_level="info" if args.dev else "warning",
    )


if __name__ == "__main__":
    main()
