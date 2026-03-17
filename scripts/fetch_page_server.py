#!/usr/bin/env python3
"""
HTTP server wrapper around fetch_page.py for use as a preview server.

Usage:
    python fetch_page_server.py [--port PORT]

API:
    GET /fetch?url=https://example.com[&timeout=30][&googlebot=1][&no_redirects=1]
    GET /health
"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from fetch_page import fetch_page, GOOGLEBOT_USER_AGENT


class FetchPageHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default Apache-style access log

    def send_json(self, status: int, data: dict):
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self.send_json(200, {"status": "ok"})
            return

        if parsed.path == "/fetch":
            params = parse_qs(parsed.query)
            url = params.get("url", [None])[0]
            if not url:
                self.send_json(400, {"error": "Missing required query param: url"})
                return

            timeout = int(params.get("timeout", ["30"])[0])
            follow_redirects = "no_redirects" not in params
            ua = GOOGLEBOT_USER_AGENT if "googlebot" in params else None

            result = fetch_page(
                url,
                timeout=timeout,
                follow_redirects=follow_redirects,
                user_agent=ua,
            )
            status = 200 if not result["error"] else 502
            self.send_json(status, result)
            return

        self.send_json(404, {"error": f"Unknown path: {parsed.path}"})


def main():
    parser = argparse.ArgumentParser(description="HTTP server wrapper for fetch_page")
    parser.add_argument("--port", type=int, default=7801, help="Port to listen on")
    args = parser.parse_args()

    server = HTTPServer(("127.0.0.1", args.port), FetchPageHandler)
    print(f"fetch_page server listening on http://127.0.0.1:{args.port}")
    print("  GET /fetch?url=https://example.com")
    print("  GET /health")
    server.serve_forever()


if __name__ == "__main__":
    main()
