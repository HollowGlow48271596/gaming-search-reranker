from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from openai import OpenAIError

from game_rerank import InfraiClient, InfraiError, RerankRequest, SearchCandidate, choose_results


class RerankHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/rerank":
            self.send_error(404)
            return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            candidates = [SearchCandidate(**item) for item in body["candidates"]]
            result = choose_results(InfraiClient(), RerankRequest(body["query"], candidates, body.get("top_k", 5)))
            payload = {"results": [item.__dict__ for item in result]}
            status = 200
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            payload = {"error": {"code": "INVALID_REQUEST", "message": str(error)}}
            status = 400
        except (InfraiError, OpenAIError, requests.RequestException) as error:
            payload = {"error": {"code": getattr(error, "code", "UPSTREAM_FAILURE"), "message": str(error)}}
            status = 502
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8000), RerankHandler).serve_forever()
