from src.extraction_service.schemas import (
    TenantSearchRequest,
    TenantSearchResponse,
    TenantSearchMatch,
)


def test_tenant_search_schema_roundtrip():
    req = TenantSearchRequest(query="hello", top_k=3)
    assert req.query == "hello"
    assert req.top_k == 3

    resp = TenantSearchResponse(matches=[
        TenantSearchMatch(file_id="f1", page_id=1, score=0.9, ocr="x", embeddings=[0.1, 0.2])
    ])
    assert resp.matches[0].file_id == "f1"

