# Business Chatbot

One multi-tenant chatbot engine, rented to small businesses. Each business = one YAML file in `tenants/`. See `plan.md`.

## Setup
```
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt
copy .env.example .env      # add ANTHROPIC_API_KEY for the real bot (costs money); without it a dumb offline mock is used
```

## Run
- **M1 CLI chat:** `.venv\Scripts\python -m app.cli demo-bakery`
- **M2-M4 server:** `.venv\Scripts\uvicorn app.main:app --reload` then open http://localhost:8000/demo/demo-bakery (phone: use your PC's LAN IP).
  - API: `POST /chat/{tenant_id}` `{"message": "...", "conversation_id": null}`
  - Embed: `<script src="https://HOST/widget/widget.js" data-tenant="demo-bakery" defer></script>`
  - Logs/leads: `/admin` (HTTP basic auth, password = `ADMIN_PASSWORD`)
- **Notifications:** set `contact_for_handoff.type` to `email` (SMTP_* vars) or `telegram` (TELEGRAM_BOT_TOKEN, value = chat id). `log` just logs.
- **Tests:** `.venv\Scripts\python -m pytest` (plumbing, no key needed)
- **Behaviour check per tenant (needs real LLM key):** `.venv\Scripts\python -m app.check_tenant demo-bakery` - run before every deploy/config change. With the mock, adversarial cases are expected to fail.

## Status
M1-M4 done and tested offline. M7 partly done (validator, case runner, admin log viewer; questionnaire template still to write).
Not started (need your accounts/decisions): **M5 deploy** (host choice, may cost money), **M6 WhatsApp** (Meta Business verification, phone number).

## Next
1. Add `ANTHROPIC_API_KEY` (set a monthly spend limit in the console), run `check_tenant` and tune prompts.
2. Pick a host for M5; start Meta business verification now for M6.
3. Answer plan.md section 12 open questions.
