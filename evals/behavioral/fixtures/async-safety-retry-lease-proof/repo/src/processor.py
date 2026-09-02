from .worker import RetryableJobError


LEASE_SECONDS = 300


def process_export(store, job: dict, now_seconds: int) -> None:
    if not store.try_claim(job["job_id"], now_seconds, LEASE_SECONDS):
        raise RetryableJobError("job lease is still active")
    store.write_export(job)
    store.mark_complete(job["job_id"])
