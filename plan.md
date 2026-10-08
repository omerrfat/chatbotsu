# plan.md — Ready-Made Business Chatbot (Side Hustle)

## 1. Situation

- I'm an AI engineering student with limited money and limited time (studies, coursework, final year project).
- I want a **digital product that earns money quickly**. Fast first income matters more than a perfect product.
- The product: **one reusable chatbot that I customise and rent to small businesses** (tuition centres, bakeries, salons, repair shops, clinics, car workshops, home-based sellers).
- These businesses answer the same questions all day on WhatsApp and their website: prices, opening hours, location, services, availability, bookings. The bot handles these 24/7 and hands anything tricky to the owner.
- Business model: **one-time setup fee + monthly subscription** per business. Once the core is built, each new client should be mostly configuration (target: under 2 hours to onboard).

## 2. Goals

1. Build a working MVP fast, demo-able to a real business owner within ~2 weeks.
2. Make it **multi-tenant from day one**: one codebase, many businesses, each defined by a config file.
3. Keep running costs very low (free tiers where possible, a cheap LLM model).
4. Make the bot **safe and trustworthy**: it never invents prices or promises, and it escalates to a human when unsure.

## 3. Non-goals (for now)

- No payment handling inside the chat.
- No self-serve sign-up or billing portal. I onboard clients manually.
- No fancy dashboard in v1. Config files plus a simple conversation log are enough.
- No voice, images or multi-language fine-tuning in v1. (The LLM can still reply in the customer's language.)

## 4. Product spec (MVP)

### Channels
- **Phase 1: website chat widget** (embeddable `<script>` tag). Fastest to ship, no approval process, great for demos.
- **Phase 2: WhatsApp** via the **official WhatsApp Business Platform (Cloud API)** from Meta.
  - Requires a Meta Business account, a dedicated phone number, and business verification. Start this process early because it can take days.
  - **Do not use unofficial WhatsApp Web automation libraries** (for example, whatsapp-web.js or Baileys) for client numbers. They break WhatsApp's terms and can get the business's number banned.
  - Check Meta's current conversation pricing before quoting clients.

### What the bot does
- Answers FAQs from the business's knowledge (services, prices, hours, location, policies).
- Collects booking or enquiry details (name, phone, service, preferred date/time) and saves them as a **lead**.
- Notifies the owner of new leads and handoffs (email, a Telegram bot, or a WhatsApp message to the owner).
- **Human handoff:** if the customer asks for a person, is upset, or asks something not in the knowledge base, the bot says a staff member will follow up and flags the conversation.
- Replies in the customer's language (English / Malay / Chinese, as configured per client).

### Guardrails (non-negotiable)
- Answer **only** from the business's config and knowledge base. If the info isn't there, say so and hand off.
- Never invent prices, discounts, availability, medical/legal advice, or guarantees.
- Never claim a booking is confirmed unless the business config says bookings are auto-confirmed. Default: "request received, the team will confirm".
- Store only the personal data needed (name, phone, enquiry). Have a short privacy note. Check local data-protection law before going live with real customer data.

## 5. Architecture

```
Customer ──► Website widget ─┐
                             ├─► Backend API (webhook + chat endpoint)
Customer ──► WhatsApp Cloud ─┘        │
                                      ├─► Tenant config loader (per business)
                                      ├─► LLM (Claude API, small/cheap model)
                                      ├─► Database (conversations, leads, handoffs)
                                      └─► Notifier (owner gets leads/handoffs)
```

### Suggested stack (keep it simple)
- **Backend:** Python + FastAPI (or Node + Express if preferred).
- **LLM:** Anthropic Claude API, using the cheapest capable model for chat. Keep the provider behind one interface so it can be swapped.
- **Knowledge:** for small businesses, put the whole FAQ and config into the system prompt. Add retrieval (RAG) only if a client's knowledge base gets large.
- **Database:** SQLite for local development; Postgres (e.g., Supabase free tier) in production.
- **Hosting:** a cheap/free host that supports a long-running web server and HTTPS webhooks (e.g., Render, Railway, Fly.io).
- **Widget:** a single vanilla JS file plus CSS, embeddable with one `<script>` tag. It takes a `tenant_id`.
- **Secrets:** `.env` file locally, the host's secret manager in production. Never commit keys.

### Tenant config (one file per business)
`tenants/<tenant_id>.yaml`
```yaml
tenant_id: sunny-bakery
business_name: Sunny Bakery
languages: [en, ms]
tone: friendly, short replies
hours: "Tue–Sun 9am–7pm, closed Monday"
location: "..."
contact_for_handoff: { type: email, value: owner@example.com }
bookings:
  enabled: true
  auto_confirm: false
  fields: [name, phone, item, pickup_date]
faq:
  - q: Do you do custom birthday cakes?
    a: Yes, order at least 3 days ahead. Prices start from ...
services:
  - name: ...
    price: ...
extra_rules:
  - Never promise same-day custom cakes.
```

### Data model (minimum)
- `tenants` (id, name, status, created_at). Config itself lives in YAML.
- `conversations` (id, tenant_id, channel, customer_id, started_at, status: open/handoff/closed)
- `messages` (id, conversation_id, role, content, created_at)
- `leads` (id, tenant_id, conversation_id, fields JSON, created_at, notified bool)

## 6. Suggested repo structure

```
chatbot/
  app/
    main.py            # FastAPI app, routes
    chat.py            # core: build prompt from tenant config, call LLM, parse result
    llm.py             # LLM provider wrapper
    tenants.py         # load/validate tenant YAML
    leads.py           # lead extraction + storage
    notify.py          # owner notifications
    channels/
      web.py           # widget endpoint
      whatsapp.py      # Cloud API webhook (phase 2)
    db.py
  widget/
    widget.js
    widget.css
  tenants/
    demo-bakery.yaml
    demo-tuition.yaml
  tests/
  .env.example
  README.md
```

## 7. Milestones

Work through these **in order**. Each one ends with something runnable.

### M1 — Core chat engine (CLI)
- Load a tenant YAML, build the system prompt, chat in the terminal.
- Implement guardrails in the prompt, plus a structured output for `handoff: true/false` and `lead: {...}`.
- **Done when:** the demo bakery bot answers FAQs correctly, refuses to invent prices, and triggers handoff on unknown questions.

### M2 — API + database
- FastAPI endpoint `POST /chat/{tenant_id}` that stores conversations and messages.
- Lead and handoff records saved to the database.
- **Done when:** a conversation via curl/Postman persists, and leads appear in the database.

### M3 — Website widget
- Embeddable chat bubble that talks to the API.
- A simple demo HTML page for each demo tenant (used for sales demos).
- **Done when:** I can open a demo page on my phone and chat with the bot.

### M4 — Owner notifications
- New lead or handoff sends a notification to the owner (start with email or a Telegram bot, since they're free).
- **Done when:** submitting a booking in the widget sends the owner a readable summary.

### M5 — Deploy
- Deploy to a cheap host with HTTPS, environment secrets, and a production database.
- **Done when:** the demo is live on a public URL I can send to prospects.

### M6 — WhatsApp channel
- Webhook for the WhatsApp Cloud API: verify the token, receive messages, reply through the same chat engine.
- Map phone numbers to conversations.
- **Done when:** messaging the test number on WhatsApp gets correct bot replies, and handoff/lead flows work.

### M7 — Onboarding kit (business side)
- A questionnaire template for collecting a new client's FAQ, prices, hours and rules.
- A script that validates a new tenant YAML and runs a set of test questions against it.
- A simple conversation log viewer (even a basic password-protected page).
- **Done when:** onboarding a new business takes under 2 hours.

## 8. Testing

- For each tenant, keep a `tests/<tenant_id>_cases.yaml` file of questions with expected behaviour (answer / refuse / handoff / lead captured).
- Include adversarial cases: "give me a discount", "is it free?", "ignore your instructions", off-topic questions, angry customers.
- Run these before every deploy and every config change.

## 9. Costs to watch

- LLM tokens: use a cheap model, cap the conversation history length, and keep prompts tight.
- WhatsApp conversation fees (check Meta's current pricing for the country).
- Hosting and database: stay on free tiers until there are paying clients.
- Set a hard monthly spending limit on the LLM API account.

## 10. Business plan (outside the code)

- **Pricing structure:** a setup fee (covers config and onboarding) plus a monthly fee (hosting, LLM costs, maintenance, small edits). Exact numbers are TBD. Price so that one client covers all running costs with a clear margin.
- **First clients:** offer 1–2 businesses I know a cheap or free pilot in exchange for a testimonial and permission to use them as a case study.
- **Outreach:** use the live demo link plus a short message showing the bot answering *their* common questions.
- **Side-project boundary:** keep this separate from my employer's work. Use my own accounts, code and time, and check there's no conflict with the company's own AI/WhatsApp bot plans or my contract.

## 11. Instructions for Claude Code

- Work milestone by milestone. Don't start a milestone until the previous one runs.
- Prefer the simplest thing that works. Avoid heavy frameworks and premature abstractions, except multi-tenancy, which is required from the start.
- Ask me before adding anything that costs money (paid APIs, hosting tiers, domains).
- Never hardcode secrets. Keep `.env.example` up to date.
- After each milestone, update `README.md` with how to run it, and list what's next.

## 12. Open questions

- Which 1–2 businesses will be the first pilots (and what type)?
- Website widget only at first, or do pilots need WhatsApp immediately?
- How should owners receive notifications: email, Telegram, or WhatsApp?
- Pricing numbers.
