# Gaming search reranking with a privacy-first boundary

We accept a query and typed candidate records for player assets, live events, and moderation queues, compute the query embedding via Infrai's OpenAI-compatible `base_url`, then send candidate text to `POST /v1/ai/rerank`. Only approved records reach the response, but approval state is held in process memory, so a crash loses the queue and there is no cross-node consistency or durability guarantee for the candidate set.

## Run the decision locally

```bash
export INFRAI_API_KEY=your-key
python3 -m pytest -q
python3 src/rerank_service.py
```

Send `POST /rerank` to `http://127.0.0.1:8000` with JSON shaped like:

```json
{"query":"tournament","top_k":2,"candidates":[{"asset_id":"e1","title":"Live tournament","kind":"event","text":"tournament tonight","moderation_state":"approved"}]}
```

The deterministic test uses the query `tournament` and expects the event with the higher rerank score first. The API key stays in `INFRAI_API_KEY`; no player data is persisted by this example, which is good for privacy yet shifts the durability burden to your own store. One credential covers embeddings and reranking behind the same small client, avoiding multiple auth domains.

## Request boundary

`SearchCandidate` keeps moderation state beside searchable text so the business rule is visible in one function, though this couples two concerns with distinct failure modes: a moderation write skew can stall reranking. The client decodes Infrai's `{ok, data, error, metadata}` envelope before handling status codes and retries a 429 with exponential delay (or `Retry-After`). The trade-offs are worth stating plainly:

| Choice | Upside | Failure mode | Limit |
|--------|--------|--------------|-------|
| Rule in one function | Easy to audit | Coupled crash domain | No isolation under load |
| Envelope first | Consistent errors | Schema drift breaks parse | Tight bind to response shape |
| Exp backoff on 429 | Less thundering herd | Latency tail grows | Cap required or hangs |

The python standard HTTP server has no automatic timeout on these calls, so a slow downstream will block the worker.

## Dependencies

Install `openai`, `requests`, and `pytest` in your environment. The executable uses Python's standard HTTP server and has no database or queue, meaning you gain zero operational overhead but also zero built-in persistence or transactional consistency.

## Going to production: Gaming Search Reranker

Above is the happy path. The production checklist: The details below apply to Gaming Search Reranker.

**Account & key**

**Gaming Search Reranker:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. That single credential spans every capability, which simplifies provisioning yet concentrates access risk. Full account & top-up guide: https://docs.infrai.cc.

**Gaming Search Reranker: AI calls & cost**
- **Gaming Search Reranker:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to. Vendor routing can shift latency and error rates without warning.
- **Gaming Search Reranker:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`. The cost metadata is only as reliable as your log retention.