"""Explicit capabilities, enforced centrally for every protected endpoint."""

ROLES = {
    "auditor": {"read"},
    "editor": {"read", "correct"},
    "operator": {"read", "operate"},
    "admin": {"read", "correct", "operate", "manage_sources", "manage_accounts"},
}


def permissions_for(role):
    return sorted(ROLES.get(role, set()))


def required_permission(method, path):
    path = path.rstrip("/")
    if path.startswith("/accounts"):
        return "manage_accounts"
    if path.startswith("/providers/") and "/preview/" in path:
        return "manage_sources"
    if method in {"GET", "HEAD", "OPTIONS"}:
        return "read"
    if path.startswith("/automation/"):
        if path == "/automation/scopes" or (
            path.startswith("/automation/scopes/") and method == "DELETE"
        ):
            return "manage_sources"
        return "operate"
    if path.startswith(("/providers/", "/catalog/")):
        return "manage_sources"
    return "correct"
