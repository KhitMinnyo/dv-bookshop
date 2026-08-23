#!/usr/bin/env python3
"""A loopback-only, dummy AWS IMDSv1/IMDSv2-style training endpoint."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys


HOST = "127.0.0.1"
PORT = 5160
TOKEN = "local-imdsv2-training-token"


IDENTITY_DOCUMENT = {
    "accountId": "000000000000",
    "architecture": "x86_64",
    "availabilityZone": "local-1a",
    "instanceId": "i-local-training-only",
    "instanceType": "local.dummy",
    "region": "local-1",
}

CREDENTIALS = {
    "Code": "Success",
    "LastUpdated": "2000-01-01T00:00:00Z",
    "Type": "AWS-HMAC",
    "AccessKeyId": "AKIALOCALONLY000000",
    "SecretAccessKey": "not-a-real-secret",
    "Token": "dummy-session-token",
    "Expiration": "2099-01-01T00:00:00Z",
}


class MetadataHandler(BaseHTTPRequestHandler):
    server_version = "LocalMetadataMock/1.0"

    def log_message(self, format_string, *args):
        sys.stderr.write("metadata-mock: " + (format_string % args) + "\n")

    def send_text(self, body, status=200, content_type="text/plain"):
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_PUT(self):
        if self.path != "/latest/api/token":
            self.send_text("not found\n", 404)
            return

        ttl = self.headers.get("X-aws-ec2-metadata-token-ttl-seconds", "")
        try:
            if not 1 <= int(ttl) <= 21600:
                raise ValueError
        except ValueError:
            self.send_text("invalid token TTL\n", 400)
            return

        self.send_text(TOKEN)

    def do_GET(self):
        if not self.path.startswith("/latest/"):
            self.send_text("not found\n", 404)
            return

        # Tokenless requests model IMDSv1. A supplied token must be the dummy
        # token issued above, which models the IMDSv2 header check.
        supplied_token = self.headers.get("X-aws-ec2-metadata-token")
        if supplied_token is not None and supplied_token != TOKEN:
            self.send_text("invalid metadata token\n", 401)
            return

        routes = {
            "/latest/meta-data/": "ami-id\ninstance-id\nlocal-ipv4\niam/security-credentials/\n",
            "/latest/meta-data/ami-id": "ami-local-training-only\n",
            "/latest/meta-data/instance-id": "i-local-training-only\n",
            "/latest/meta-data/local-ipv4": "127.0.0.1\n",
            "/latest/meta-data/iam/security-credentials/": "lab-role\n",
            "/latest/meta-data/iam/security-credentials/lab-role": json.dumps(CREDENTIALS) + "\n",
            "/latest/dynamic/instance-identity/document": json.dumps(IDENTITY_DOCUMENT) + "\n",
        }
        body = routes.get(self.path)
        if body is None:
            self.send_text("not found\n", 404)
            return
        content_type = "application/json" if body.startswith("{") else "text/plain"
        self.send_text(body, content_type=content_type)


def main():
    server = ThreadingHTTPServer((HOST, PORT), MetadataHandler)
    print(f"Local metadata mock listening on http://{HOST}:{PORT}")
    print("This process serves dummy data only and makes no cloud requests.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping local metadata mock.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
