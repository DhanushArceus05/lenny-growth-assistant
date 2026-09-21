async def test_create_and_fetch_session(client):
    create_resp = await client.post("/api/sessions", json={"title": "Pricing questions"})
    assert create_resp.status_code == 201
    session = create_resp.json()
    assert session["title"] == "Pricing questions"

    get_resp = await client.get(f"/api/sessions/{session['id']}")
    assert get_resp.status_code == 200
    detail = get_resp.json()
    assert detail["id"] == session["id"]
    assert detail["messages"] == []


async def test_get_missing_session_returns_404(client):
    resp = await client.get("/api/sessions/does-not-exist")
    assert resp.status_code == 404


async def test_list_sessions_orders_by_recency(client):
    await client.post("/api/sessions", json={"title": "First"})
    await client.post("/api/sessions", json={"title": "Second"})
    resp = await client.get("/api/sessions")
    assert resp.status_code == 200
    titles = [s["title"] for s in resp.json()]
    assert "First" in titles and "Second" in titles


async def test_session_default_title_when_omitted(client):
    resp = await client.post("/api/sessions", json={})
    assert resp.status_code == 201
    assert resp.json()["title"] == "New conversation"
