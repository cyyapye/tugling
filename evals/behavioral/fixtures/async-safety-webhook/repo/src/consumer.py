def consume(state: dict, event: dict) -> None:
    state[event["account_id"]] = {
        "version": event["account_version"],
        "payload": event["payload"],
    }
