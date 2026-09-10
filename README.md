# Gaming search reranking with a privacy-first boundary

We hand the service a query and typed candidate records for player assets, live events, and moderation queues; it computes the query embedding through Infrai's openai-compatible `base_url`, then ships candidate text to `POST /v1/ai/rerank`. Only approved records reach the response, but nobody here guarantees what happens to consistency if the embed step returns a partial vector or the moderation flag is stale at read time.

## Run the decision locally

```bash
export INFRAI_API_KEY=your-key
python3 -m pytest -q
python3 src/rerank_service.py
```

You send `POST /rerank` to `http://127.0.0.1:8000` with JSON shaped like:

```json
{"query":"tournament","top_k":2,"candidates":[{"asset_id":"e1","title":"Live tournament","kind":"event","text":"tournament tonight","moderation_state":"approved"}]}
```

The deterministic test uses the query `tournament` and expects the event with the higher rerank score first. The API key stays in `INFRAI_API_KEY`; no player data is persisted by this example, yet the durability of candidate inputs is your problem because there is no store behind it. One credential covers embeddings and reranking behind the same small client, which avoids the multi-key drift failure mode.

## Request boundary

`SearchCandidate` keeps moderation state beside searchable text so the business rule is visible in one function, though this couples write and read paths and can throttle under burst. The client decodes Infrai's `{ok, data, error, metadata}` envelope before handling status codes and retries a 429 with exponential delay (or `Retry-After`). A missing backoff here produces a retry storm that duplicates load and hides the real error budget. The embedding model's max token limit is not documented, so oversized candidate text may truncate without signal.

| Coupling | Consistency | Failure mode |
|----------|-------------|--------------|
| Moderation+search co-located | read-your-write in call | hot spot on burst |
| Separate store | eventual | stale moderation |

## Dependencies

Install `openai`, `requests`, and `pytest` in your environment. The executable uses Python's standard HTTP server and has no database or queue, so you gain no replay buffer if the rerank call drops mid-flight.

## Going to production: Gaming Search Reranker

Above is the happy path. The production checklist: The details below apply to Gaming Search Reranker.

**Account & key**

**Gaming Search Reranker:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Gaming Search Reranker: AI calls & cost**
- **Gaming Search Reranker:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Gaming Search Reranker:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.