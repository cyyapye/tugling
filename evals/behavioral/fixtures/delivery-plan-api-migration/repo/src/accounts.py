ACCOUNTS = {
    "acct-001": {"id": "acct-001", "username": "river"},
    "acct-002": {"id": "acct-002", "username": "stone"},
}


def lookup_by_username(username: str) -> dict[str, str] | None:
    return next((row for row in ACCOUNTS.values() if row["username"] == username), None)
