#!/usr/bin/env python3
"""The Cypher Sentinel — Cybersecurity & Privacy News, Victorian Style."""

import argparse
import http.server
import functools
import os
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from config import EDITIONS_DIR, SERVE_PORT

PROJECT_ROOT = Path(__file__).resolve().parent

CST = timezone(timedelta(hours=-6))


class NewspaperHandler(http.server.SimpleHTTPRequestHandler):
    """Serves editions dir, routing / to latest.html and /tts for audio."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(EDITIONS_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/" or self.path == "":
            self.path = "/latest.html"
        super().do_GET()

    def do_POST(self):
        if self.path == "/tts":
            self._handle_tts()
        else:
            self.send_error(404)

    def _handle_tts(self):
        import json
        from tts import synthesize_wav

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0 or content_length > 50000:
            self.send_error(400, "Text required (max 50KB)")
            return

        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
            text = data.get("text", "").strip()
        except (json.JSONDecodeError, AttributeError):
            self.send_error(400, "Invalid JSON")
            return

        if not text:
            self.send_error(400, "No text provided")
            return

        try:
            wav_bytes = synthesize_wav(text)
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(wav_bytes)))
            self.end_headers()
            self.wfile.write(wav_bytes)
        except Exception as e:
            print(f"[TTS] Error: {e}")
            self.send_error(500, "TTS synthesis failed")


def git_push_edition():
    """Stage editions/, commit with today's date, and push to origin.
    Returns True on success, False on failure."""
    today = datetime.now(CST).strftime("%Y-%m-%d")
    try:
        run = functools.partial(subprocess.run, cwd=PROJECT_ROOT, check=True,
                                capture_output=True, text=True)
        run(["git", "add", "editions/"])
        # Check if there's anything to commit
        result = subprocess.run(["git", "diff", "--cached", "--quiet"],
                                cwd=PROJECT_ROOT)
        if result.returncode == 0:
            print("  No edition changes to push.")
            return True
        run(["git", "commit", "-m", f"Add edition {today}"])
        run(["git", "push", "origin", "master"])
        print(f"  Pushed edition {today} to origin/master.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  Git push failed: {e.stderr or e}")
        return False


def cmd_generate(args):
    from generator import build_edition
    build_edition(send_telegram=not args.no_telegram)


def cmd_serve(args):
    port = args.port or int(os.environ.get("PORT", SERVE_PORT))
    EDITIONS_DIR.mkdir(parents=True, exist_ok=True)

    # Create a placeholder if no edition exists yet
    latest = EDITIONS_DIR / "latest.html"
    if not latest.exists():
        latest.write_text("<html><body><h1>The Cypher Sentinel</h1><p>No edition generated yet. Run: python3 main.py generate</p></body></html>")

    server = http.server.HTTPServer(("0.0.0.0", port), NewspaperHandler)

    print(f"\n  The Cypher Sentinel is being served at:")
    print(f"  http://localhost:{port}/\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Press stopped. Stay vigilant, dear reader.")
        server.shutdown()


def cmd_run(args):
    from generator import build_edition
    path = build_edition(send_telegram=not args.no_telegram)
    if path:
        cmd_serve(args)


def cmd_schedule(args):
    import schedule

    def job():
        now = datetime.now(CST)
        print(f"\n  [{now.strftime('%Y-%m-%d %H:%M %Z')}] Generating today's edition...")
        from generator import build_edition
        from processor import generate_telegram_digest
        from telegram_bot import send_edition_to_telegram
        try:
            # Generate WITHOUT telegram — send only after successful push
            build_edition(send_telegram=False)
            print("  Edition generated successfully.")
            pushed = git_push_edition()
            # Send Telegram only after git push succeeds
            if pushed and not args.no_telegram:
                print("  Sending Telegram digest...")
                date_fancy = datetime.now(CST).strftime("%B %d, %Y")
                send_edition_to_telegram(
                    f"New edition is live!\n\nhttps://the-cypher-sentinel.up.railway.app/",
                    date_fancy,
                )
                print("  Telegram sent.")
            elif not pushed:
                print("  Skipped Telegram — git push failed.")
        except Exception as e:
            print(f"  Error generating edition: {e}")

    schedule.every().day.at("08:30").do(job)

    now = datetime.now(CST)
    print(f"\n  The Cypher Sentinel — Scheduler active")
    print(f"  Current time (CST): {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Next edition at:    08:30 CST daily")
    print(f"  Press Ctrl+C to stop.\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n  Scheduler stopped. Stay vigilant, dear reader.")


def main():
    parser = argparse.ArgumentParser(
        description="The Cypher Sentinel — Guarding the Gates of the Digital Dominion",
    )
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="Fetch news and generate today's edition")
    gen.add_argument("--no-telegram", action="store_true", help="Skip Telegram notification")
    gen.set_defaults(func=cmd_generate)

    srv = sub.add_parser("serve", help="Serve the newspaper locally")
    srv.add_argument("--port", type=int, default=None, help=f"Port (default: {SERVE_PORT})")
    srv.set_defaults(func=cmd_serve)

    run = sub.add_parser("run", help="Generate then serve")
    run.add_argument("--port", type=int, default=None, help=f"Port (default: {SERVE_PORT})")
    run.add_argument("--no-telegram", action="store_true", help="Skip Telegram notification")
    run.set_defaults(func=cmd_run)

    sched = sub.add_parser("schedule", help="Run scheduler — generates edition daily at 8:30 AM CST")
    sched.add_argument("--no-telegram", action="store_true", help="Skip Telegram notification")
    sched.set_defaults(func=cmd_schedule)

    args = parser.parse_args()

    # Default to serve if no command given (for Railway/deployment)
    if args.command is None:
        args.port = None
        args.no_telegram = False
        cmd_serve(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
