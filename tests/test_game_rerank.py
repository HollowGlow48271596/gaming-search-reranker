from src.game_rerank import RerankRequest, SearchCandidate, choose_results


class StubClient:
    def embed(self, text):
        return [0.1, 0.2]

    def rerank(self, request):
        return [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.4}]


def test_rerank_prioritizes_relevant_approved_asset():
    candidates = [
        SearchCandidate("a1", "Arena", "asset", "arena map", "approved"),
        SearchCandidate("e1", "Live tournament", "event", "tournament tonight", "approved"),
    ]
    result = choose_results(StubClient(), RerankRequest("tournament", candidates, 2))
    assert [item.asset_id for item in result] == ["e1", "a1"]
