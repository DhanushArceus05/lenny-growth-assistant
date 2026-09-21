async def test_health_reports_database_ok(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["database"] is True
    # vector_index_populated is False because transcript_chunks (pgvector-only) doesn't
    # exist in the sqlite test DB — this correctly reflects "not ingested yet", not a bug.
    assert body["vector_index_populated"] is False
    assert {p["name"] for p in body["providers"]} == {"ollama", "anthropic"}
