"""M7: validate a tenant and run its test cases.   python -m app.check_tenant demo-bakery
Real bot quality is only judged with a real LLM (set ANTHROPIC_API_KEY); the mock is plumbing-only."""
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

from .chat import respond  # noqa: E402
from .llm import get_provider  # noqa: E402
from .tenants import TENANT_DIR, load_tenant, validate  # noqa: E402

CASES_DIR = Path(__file__).resolve().parent.parent / "tests"


def run_case(tenant, llm, case):
    """case: {say: str | [str], expect: handoff|answer|lead, contains: [..], not_contains: [..]}"""
    says = case["say"] if isinstance(case["say"], list) else [case["say"]]
    history, last, lead = [], None, None
    for s in says:
        last = respond(tenant, history, s, llm, lead_already_saved=lead is not None)
        lead = last.lead or lead
        history += [{"role": "user", "content": s}, {"role": "assistant", "content": last.reply}]
    problems = []
    exp = case.get("expect", "answer")
    if exp == "handoff" and not last.handoff:
        problems.append("expected handoff")
    if exp == "answer" and last.handoff:
        problems.append("unexpected handoff")
    if exp == "lead" and not lead:
        problems.append("expected lead to be captured")
    low = last.reply.lower()
    problems += [f"missing '{c}'" for c in case.get("contains", []) if c.lower() not in low]
    problems += [f"must not contain '{c}'" for c in case.get("not_contains", []) if c.lower() in low]
    return problems, last.reply


def main():
    tid = sys.argv[1]
    import yaml as _y
    cfg = _y.safe_load((TENANT_DIR / f"{tid}.yaml").read_text(encoding="utf-8"))
    errs = validate(cfg)
    if errs:
        print("INVALID CONFIG:\n  " + "\n  ".join(errs))
        sys.exit(1)
    print(f"config OK: {tid}")
    tenant, llm = load_tenant(tid), get_provider()
    cases_file = CASES_DIR / f"{tid}_cases.yaml"
    if not cases_file.exists():
        print(f"no {cases_file.name}; skipping behaviour tests")
        return
    cases, failed = yaml.safe_load(cases_file.read_text(encoding="utf-8")), 0
    print(f"provider: {type(llm).__name__}")
    for c in cases:
        problems, reply = run_case(tenant, llm, c)
        failed += bool(problems)
        print(f"[{'FAIL' if problems else 'ok  '}] {c['say']!r}" + (f"\n       {problems}\n       reply: {reply}" if problems else ""))
    print(f"\n{len(cases) - failed}/{len(cases)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
