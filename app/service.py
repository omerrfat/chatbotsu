"""Channel-agnostic turn handling, shared by the web widget and (later) WhatsApp."""
from . import db, notify
from .chat import respond
from .llm import LLMProvider

MAX_MESSAGES_PER_CONVERSATION = 60  # cost guard against runaway/abusive chats
LIMIT_REPLY = "This conversation has reached its length limit. A team member will follow up with you."


def handle_message(conn, tenant: dict, llm: LLMProvider, channel: str, text: str,
                   conversation_id: str | None = None, customer_id: str | None = None):
    """Returns (conversation_id, ChatResult-like dict, notifications_to_send)."""
    tid = tenant["tenant_id"]
    conv = db.get_conversation(conn, conversation_id, tid) if conversation_id else None
    cid = conv["id"] if conv else db.new_conversation(conn, tid, channel, customer_id)

    if db.count_messages(conn, cid) >= MAX_MESSAGES_PER_CONVERSATION:
        return cid, {"reply": LIMIT_REPLY, "handoff": True, "lead": None}, []

    history = db.get_history(conn, cid)
    result = respond(tenant, history, text, llm, lead_already_saved=db.has_lead(conn, cid))
    db.add_message(conn, cid, "user", text)
    db.add_message(conn, cid, "assistant", result.reply)

    jobs = []
    transcript = history + [{"role": "user", "content": text}, {"role": "assistant", "content": result.reply}]
    if result.lead:
        lead_id = db.add_lead(conn, tid, cid, result.lead)
        jobs.append(("lead", lead_id, result.lead, "", transcript))
    if result.handoff:
        if not conv or conv["status"] != "handoff":  # notify once per conversation
            jobs.append(("handoff", None, None, result.handoff_reason, transcript))
        db.set_status(conn, cid, "handoff")
    return cid, {"reply": result.reply, "handoff": result.handoff, "lead": result.lead is not None}, jobs


def run_notifications(db_conn_factory, tenant: dict, jobs):
    """Runs after the HTTP response (background task) so chat latency isn't affected."""
    conn = db_conn_factory()
    try:
        for kind, lead_id, fields, reason, transcript in jobs:
            ok = notify.send(tenant, kind, fields, reason, transcript)
            if ok and lead_id:
                db.mark_notified(conn, lead_id)
    finally:
        conn.close()
