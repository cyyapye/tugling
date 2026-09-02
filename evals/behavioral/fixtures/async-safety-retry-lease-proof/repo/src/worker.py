from collections.abc import Callable


class RetryableJobError(Exception):
    pass


def handle_export_message(message, process_export: Callable[[dict], None]) -> None:
    try:
        process_export(message.body)
    except RetryableJobError:
        message.retry(delay_seconds=60)
    else:
        message.ack()
