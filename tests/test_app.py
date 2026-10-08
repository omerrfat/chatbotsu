"""Plumbing tests with a scripted fake LLM (no API key, no network)."""
import json

import pytest
from fastapi.testclient import TestClient

from app import chat, db, tenants
from app.llm import LLMProvider


class Scripted(LLMProvider):
    def __init__(self, *outputs):
        self.outputs, self.calls = list(outputs), []

    def complete(self, system, messages):
        self.calls.append((system, messages))
        return self.outputs.pop(0) if self.outputs else json.dumps({"reply": "ok", "handoff": False, "lead": None})


def out(reply="hi", handoff=False, lead=None, reason=""):
    return json.dumps({"reply": reply, "handoff": handoff, "handoff_reason": reason, "lead": lead})


@pytest.fixture
def tenant():
    return tenants.load_tenant("demo-bakery")


def test_all_tenants_valid():
    for t in tenants.list_tenants():
        tenants.load_tenant(t)


def test_validate_catches_problems():
    assert tenants.validate({"tenant_id": "Bad ID"})


def test_prompt_contains_guardrails_and_data(tenant):
    p = chat.build_system_prompt(tenant)
    assert "NEVER invent" in p and "RM 95" in p and "NEVER confirmed" in p and "Never promise same-day" in p
    assert '["name", "phone", "item", "pickup_date"]' in p


def test_auto_confirm_changes_rule(tenant):
    tenant = {**tenant, "bookings": {**tenant["bookings"], "auto_confirm": True}}
    assert "may tell the customer their booking is confirmed" in chat.build_system_prompt(tenant)


def test_bad_json_fails_safe_to_handoff(tenant):
    r = chat.respond(tenant, [], "hello", Scripted("not json at all"))
    assert r.handoff and r.lead is None


def test_json_wrapped_in_text_is_parsed(tenant):
    r = chat.respond(tenant, [], "hi", Scripted("Sure!\n" + out("hello there")))
    assert r.reply == "hello there"


def test_incomplete_lead_dropped(tenant):
    r = chat.respond(tenant, [], "hi", Scripted(out(lead={"name": "A", "phone": ""})))
    assert r.lead is None


def test_complete_lead_kept_and_filtered(tenant):
    lead = {"name": "A", "phone": "1", "item": "cake", "pickup_date": "Sat", "extra": "x"}
    r = chat.respond(tenant, [], "hi", Scripted(out(lead=lead)))
    assert r.lead == {"name": "A", "phone": "1", "item": "cake", "pickup_date": "Sat"}


def test_history_capped_and_starts_with_user(tenant):
    hist = [{"role": "user" if i % 2 == 0 else "assistant", "content": str(i)} for i in range(50)]
    llm = Scripted(out())
    chat.respond(tenant, hist, "new", llm)
    msgs = llm.calls[0][1]
    assert len(msgs) <= chat.MAX_HISTORY and msgs[0]["role"] == "user" and msgs[-1]["content"] == "new"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    from app import main
    main._hits.clear()
    main.llm = Scripted()
    return TestClient(main.app), main


def test_unknown_tenant_404(client):
    c, _ = client
    assert c.post("/chat/nope", json={"message": "hi"}).status_code == 404
    assert c.post("/chat/..%2Fsecrets", json={"message": "hi"}).status_code == 404


def test_chat_persists_and_lead_flow(client):
    c, main = client
    lead = {"name": "A", "phone": "1", "item": "cake", "pickup_date": "Sat"}
    main.llm = Scripted(out("Hello!"), out("Request received", lead=lead), out("Anything else?", lead=lead))
    r1 = c.post("/chat/demo-bakery", json={"message": "hi"}).json()
    cid = r1["conversation_id"]
    r2 = c.post("/chat/demo-bakery", json={"message": "details", "conversation_id": cid}).json()
    assert r2["lead"] is True and r2["conversation_id"] == cid
    r3 = c.post("/chat/demo-bakery", json={"message": "more", "conversation_id": cid}).json()
    assert r3["lead"] is False  # not saved twice
    conn = db.connect()
    assert conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 6
    assert conn.execute("SELECT notified FROM leads").fetchone()[0] == 1  # 'log' notifier delivered


def test_handoff_marks_conversation(client):
    c, main = client
    main.llm = Scripted(out("A staff member will follow up", handoff=True, reason="unknown"))
    cid = c.post("/chat/demo-bakery", json={"message": "weird q"}).json()["conversation_id"]
    assert db.connect().execute("SELECT status FROM conversations WHERE id=?", (cid,)).fetchone()[0] == "handoff"


def test_conversation_isolated_between_tenants(client):
    c, _ = client
    cid = c.post("/chat/demo-bakery", json={"message": "hi"}).json()["conversation_id"]
    other = c.post("/chat/demo-tuition", json={"message": "hi", "conversation_id": cid}).json()
    assert other["conversation_id"] != cid


def test_rate_limit_and_validation(client):
    c, main = client
    assert c.post("/chat/demo-bakery", json={"message": ""}).status_code == 422
    assert c.post("/chat/demo-bakery", json={"message": "x" * 1001}).status_code == 422
    main.RATE_LIMIT = 2
    main._hits.clear()
    codes = [c.post("/chat/demo-bakery", json={"message": "hi"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    main.RATE_LIMIT = 20


def test_admin_requires_password(client):
    c, _ = client
    assert c.get("/admin").status_code == 401
    assert c.get("/admin", auth=("a", "wrong")).status_code == 401
    assert c.get("/admin", auth=("a", "secret")).status_code == 200


def test_public_and_demo_and_widget(client):
    c, _ = client
    assert c.get("/tenants/demo-bakery/public").json()["business_name"] == "Sunny Bakery"
    assert 'data-tenant="demo-bakery"' in c.get("/demo/demo-bakery").text
    assert c.get("/widget/widget.js").status_code == 200
