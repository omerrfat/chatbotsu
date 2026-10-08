"""Load and validate tenant YAML configs (one file per business)."""
import re
from pathlib import Path

import yaml

TENANT_DIR = Path(__file__).resolve().parent.parent / "tenants"
VALID_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}$")
HANDOFF_TYPES = {"email", "telegram", "log"}


class TenantError(Exception):
    pass


def validate(cfg: dict) -> list[str]:
    """Return a list of problems (empty list = valid)."""
    errs = []
    if not isinstance(cfg, dict):
        return ["config must be a YAML mapping"]
    for key in ("tenant_id", "business_name", "hours", "contact_for_handoff"):
        if not cfg.get(key):
            errs.append(f"missing required field: {key}")
    tid = str(cfg.get("tenant_id", ""))
    if tid and not VALID_ID.match(tid):
        errs.append("tenant_id must be lowercase letters, digits and hyphens")
    h = cfg.get("contact_for_handoff") or {}
    if h and (h.get("type") not in HANDOFF_TYPES or not h.get("value")):
        errs.append(f"contact_for_handoff needs type in {sorted(HANDOFF_TYPES)} and a value")
    if not cfg.get("faq") and not cfg.get("services"):
        errs.append("need at least one faq or service entry")
    for i, item in enumerate(cfg.get("faq") or []):
        if not (isinstance(item, dict) and item.get("q") and item.get("a")):
            errs.append(f"faq[{i}] needs q and a")
    for i, item in enumerate(cfg.get("services") or []):
        if not (isinstance(item, dict) and item.get("name")):
            errs.append(f"services[{i}] needs a name")
    b = cfg.get("bookings") or {}
    if b.get("enabled") and not b.get("fields"):
        errs.append("bookings.enabled is true but bookings.fields is empty")
    return errs


def load_tenant(tenant_id: str) -> dict:
    if not VALID_ID.match(tenant_id or ""):
        raise TenantError("unknown tenant")
    path = TENANT_DIR / f"{tenant_id}.yaml"
    if not path.exists():
        raise TenantError("unknown tenant")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    errs = validate(cfg)
    if errs:
        raise TenantError(f"{tenant_id}: " + "; ".join(errs))
    if cfg["tenant_id"] != tenant_id:
        raise TenantError(f"{tenant_id}: tenant_id in file does not match filename")
    return cfg


def list_tenants() -> list[str]:
    return sorted(p.stem for p in TENANT_DIR.glob("*.yaml"))
