"""CLI entry point for nocode-agent."""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="nocode-agent",
        description="No-Code Agent — visual AI workflow builder. Run locally with one command.",
    )
    sub = parser.add_subparsers(dest="command")

    start_cmd = sub.add_parser("start", help="Start the No-Code Agent server")
    start_cmd.add_argument(
        "--port", type=int, default=8000, help="Port to listen on (default: 8000)"
    )
    start_cmd.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)"
    )
    start_cmd.add_argument(
        "--no-browser", action="store_true", help="Don't auto-open the browser"
    )

    args = parser.parse_args()

    if args.command != "start":
        parser.print_help()
        sys.exit(0)

    # Lazy imports so --help stays fast
    import threading
    import webbrowser
    import uvicorn
    from .config import STATIC_DIR, DATA_DIR, AUTH_ENABLED

    url = f"http://{args.host}:{args.port}"

    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║        No-Code Agent  v1.0.0         ║")
    print("  ╚══════════════════════════════════════╝")
    print(f"  📁  Data directory : {DATA_DIR}")
    if STATIC_DIR:
        print(f"  🌐  Frontend       : {STATIC_DIR}")
    else:
        print("  ⚠️   Frontend not built. Run:  python build.py")
        print("       Or use Vite dev server:  cd frontend && npm run dev")
    print(f"  🔐  Auth required  : {'yes' if AUTH_ENABLED else 'no  (single-user local mode)'}")
    print(f"  🔗  Open in browser: {url}")
    print()

    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    uvicorn.run(
        "nocode_agent.main:app",
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
