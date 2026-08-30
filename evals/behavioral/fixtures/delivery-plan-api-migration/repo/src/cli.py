from src.accounts import lookup_by_username


def render_account(username: str) -> str:
    account = lookup_by_username(username)
    return account["id"] if account else "not found"
