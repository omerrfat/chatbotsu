"""FastAPI app: chat endpoint, widget assets, demo pages, simple admin log viewer."""
import hmac
import html
import json
import os
import time
from collections import defaultdict, deque
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402
from fastapi.security import HTTPBasic, HTTPBasicCredentials  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from . import db, service  # noqa: E402
from .llm import get_provider  # noqa: E402
from .tenants import TenantError, list_tenants, load_tenant  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Business Chatbot", docs_url=None, redoc_url=None)
# The widget runs on clients' websites, so the chat API must accept cross-origin calls.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])
app.mount("/widget", StaticFiles(directory=ROOT / "widget"), name="widget")

llm = get_provider()
_hits: dict[str, deque] = defaultdict(deque)
RATE_LIMIT, RATE_WINDOW = int(os.getenv("RATE_LIMIT", "20")), 60  # msgs per IP per minute


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = Field(default=None, max_length=64)


def _tenant_or_404(tenant_id):
    try:
        return load_tenant(tenant_id)
    except TenantError:
        raise HTTPException(404, "Unknown business")


def _rate_limit(request: Request):
    ip = request.client.host if request.client else "?"
    q, now = _hits[ip], time.monotonic()
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        raise HTTPException(429, "Too many messages, please slow down.")
    q.append(now)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/tenants/{tenant_id}/public")
def public_config(tenant_id: str):
    t = _tenant_or_404(tenant_id)
    return {"business_name": t["business_name"], "brand_color": t.get("brand_color", "#cc785c"),
            "greeting": t.get("greeting", f"Hi! Ask me anything about {t['business_name']}.")}


@app.post("/chat/{tenant_id}")
def chat(tenant_id: str, body: ChatIn, background: BackgroundTasks, _=Depends(_rate_limit)):
    tenant = _tenant_or_404(tenant_id)
    conn = db.connect()
    try:
        cid, out, jobs = service.handle_message(conn, tenant, llm, "web", body.message.strip(), body.conversation_id)
    finally:
        conn.close()
    if jobs:
        background.add_task(service.run_notifications, db.connect, tenant, jobs)
    return {"conversation_id": cid, **out}


@app.get("/demo/{tenant_id}", response_class=HTMLResponse)
def demo_page(tenant_id: str):
    t = _tenant_or_404(tenant_id)
    name = html.escape(t["business_name"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{name} - demo</title>
<style>body{{font-family:system-ui,sans-serif;background:#faf9f5;color:#141413;max-width:640px;margin:10vh auto;padding:0 20px}}
h1{{font-family:Georgia,serif;font-weight:400;font-size:2.2rem}}p{{color:#3d3d3a;line-height:1.6}}</style></head>
<body><h1>{name}</h1><p>This is a demo page. Tap the chat bubble in the corner to talk to the assistant.</p>
<script src="/widget/widget.js" data-tenant="{html.escape(tenant_id)}" defer></script></body></html>"""


# ---- M7: password-protected conversation log viewer ----
_basic = HTTPBasic()


def _admin(creds: HTTPBasicCredentials = Depends(_basic)):
    pw = os.getenv("ADMIN_PASSWORD")
    if not pw or not hmac.compare_digest(creds.password.encode(), pw.encode()):
        raise HTTPException(401, "Unauthorized", headers={"WWW-Authenticate": "Basic"})


@app.get("/admin", response_class=HTMLResponse)
def admin_index(_=Depends(_admin)):
    conn = db.connect()
    rows = conn.execute("""SELECT c.id, c.tenant_id, c.channel, c.started_at, c.status,
        (SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.id) n,
        (SELECT COUNT(*) FROM leads l WHERE l.conversation_id=c.id) leads
        FROM conversations c ORDER BY c.started_at DESC LIMIT 200""").fetchall()
    conn.close()
    trs = "".join(f"<tr><td>{html.escape(r['started_at'])}</td><td>{html.escape(r['tenant_id'])}</td>"
                  f"<td>{r['status']}</td><td>{r['n']}</td><td>{r['leads']}</td>"
                  f"<td><a href='/admin/c/{r['id']}'>view</a></td></tr>" for r in rows)
    return _page("Conversations", f"<table><tr><th>Started (UTC)</th><th>Business</th><th>Status</th>"
                                  f"<th>Msgs</th><th>Leads</th><th></th></tr>{trs}</table>"
                                  f"<p><a href='/admin/leads'>All leads</a></p>")


@app.get("/admin/c/{cid}", response_class=HTMLResponse)
def admin_conv(cid: str, _=Depends(_admin)):
    conn = db.connect()
    msgs = conn.execute("SELECT role, content, created_at FROM messages WHERE conversation_id=? ORDER BY id", (cid,)).fetchall()
    conn.close()
    body = "".join(f"<p class='{m['role']}'><b>{m['role']}</b> <small>{m['created_at']}</small><br>"
                   f"{html.escape(m['content'])}</p>" for m in msgs)
    return _page("Conversation", body + "<p><a href='/admin'>back</a></p>")


@app.get("/admin/leads", response_class=HTMLResponse)
def admin_leads(_=Depends(_admin)):
    conn = db.connect()
    rows = conn.execute("SELECT * FROM leads ORDER BY id DESC LIMIT 200").fetchall()
    conn.close()
    trs = "".join(f"<tr><td>{r['created_at']}</td><td>{html.escape(r['tenant_id'])}</td>"
                  f"<td>{html.escape(', '.join(f'{k}: {v}' for k, v in json.loads(r['fields']).items()))}</td>"
                  f"<td>{'yes' if r['notified'] else 'NO'}</td></tr>" for r in rows)
    return _page("Leads", f"<table><tr><th>Created</th><th>Business</th><th>Details</th><th>Notified</th></tr>{trs}</table>"
                          "<p><a href='/admin'>back</a></p>")


def _page(title, body):
    return (f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{title}</title><style>body{{font-family:system-ui;max-width:900px;margin:30px auto;padding:0 16px;"
            f"background:#faf9f5;color:#141413}}td,th{{padding:6px 10px;border-bottom:1px solid #e6dfd8;text-align:left}}"
            f".user{{background:#efe9de;padding:8px;border-radius:8px}}.assistant{{padding:8px}}</style><h1>{title}</h1>{body}")
