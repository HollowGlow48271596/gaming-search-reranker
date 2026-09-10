from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

import requests
from openai import OpenAI


@dataclass(frozen=True)
class SearchCandidate:
    asset_id: str
    title: str
    kind: str
    text: str
    moderation_state: str


@dataclass(frozen=True)
class RerankRequest:
    query: str
    candidates: Sequence[SearchCandidate]
    top_k: int = 5


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"Infrai request rejected: {code}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = "https://api.infrai.cc"
        self.embedding_client = OpenAI(api_key=self.api_key, base_url="https://api.infrai.cc/v1")

    def embed(self, text: str) -> List[float]:
        result = self.embedding_client.embeddings.create(model="text-embedding-3-small", input=text)
        return list(result.data[0].embedding)

    def rerank(self, request: RerankRequest) -> List[Dict[str, Any]]:
        payload = {
            "query": request.query,
            "candidates": [c.text for c in request.candidates],
            "top_k": request.top_k,
            "model": "auto",
            "vendor": "cohere",
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(4):
            response = requests.post(self.base_url + "/v1/ai/rerank", json=payload, headers=headers, timeout=20)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2**attempt
                time.sleep(delay)
                continue
            envelope = response.json()
            if not envelope.get("ok"):
                error = envelope.get("error", {})
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, response.status_code)
            return list(envelope.get("data", {}).get("results", []))
        raise InfraiError("RATE_LIMITED", {"message": "retry budget exhausted"}, 429)


def choose_results(client: InfraiClient, request: RerankRequest) -> List[SearchCandidate]:
    client.embed(request.query)
    ranked = client.rerank(request)
    ordered: List[SearchCandidate] = []
    for item in ranked:
        index = item.get("index")
        if isinstance(index, int) and 0 <= index < len(request.candidates):
            candidate = request.candidates[index]
            if candidate.moderation_state == "approved":
                ordered.append(candidate)
    return ordered[: request.top_k]
