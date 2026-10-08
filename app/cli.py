"""M1: chat with a tenant in the terminal.  python -m app.cli demo-bakery"""
import sys

from dotenv import load_dotenv

load_dotenv()

from .chat import respond  # noqa: E402
from .llm import get_provider  # noqa: E402
from .tenants import load_tenant  # noqa: E402


def main():
    tenant = load_tenant(sys.argv[1] if len(sys.argv) > 1 else "demo-bakery")
    llm = get_provider()
    print(f"[{tenant['business_name']}] provider={type(llm).__name__}. Ctrl+C to quit.\n")
    history, lead_saved = [], False
    while True:
        try:
            msg = input("you> ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not msg:
            continue
        r = respond(tenant, history, msg, llm, lead_saved)
        history += [{"role": "user", "content": msg}, {"role": "assistant", "content": r.reply}]
        print(f"bot> {r.reply}")
        if r.handoff:
            print(f"     [HANDOFF: {r.handoff_reason}]")
        if r.lead:
            lead_saved = True
            print(f"     [LEAD: {r.lead}]")


if __name__ == "__main__":
    main()
