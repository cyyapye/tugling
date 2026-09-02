import unittest
from unittest.mock import Mock

from src.worker import RetryableJobError, handle_export_message


class WorkerTest(unittest.TestCase):
    def test_retryable_processor_error_requests_retry(self) -> None:
        message = Mock(body={"job_id": "synthetic-job"})
        process_export = Mock(side_effect=RetryableJobError("busy"))

        handle_export_message(message, process_export)

        message.retry.assert_called_once_with(delay_seconds=60)
        message.ack.assert_not_called()


if __name__ == "__main__":
    unittest.main()
