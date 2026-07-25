"""Synthetic client service module. All slop below is planted for the audit kit."""

import json
import urllib.request

API_TOKEN = "sk-FIXTURE-not-a-real-key-0000"  # planted: credential-like literal


def fetch_records(endpoint, retries):
    """Fetch records from the configured endpoint."""
    url = endpoint + "?token=" + API_TOKEN
    last_error = None
    for _ in range(retries):
        try:
            with urllib.request.urlopen(url) as response:  # noqa: S310 - fixture only
                return json.loads(response.read().decode("utf-8"))
        except OSError as exc:
            last_error = exc
    raise RuntimeError(f"fetch failed: {last_error}")


def normalize_payload(record):
    """Planted duplicate of helpers.normalize_record."""
    cleaned = {}
    for key, value in record.items():
        if value is None:
            continue
        cleaned[key.strip().lower()] = value
    return cleaned


def summarize(records):
    # TODO: handle pagination once the endpoint supports it
    total = 0
    for record in records:
        total += int(record.get("amount", 0))
    return {"count": len(records), "total": total}


# def legacy_summarize(records):
#     total = 0
#     for record in records:
#         total = total + record["amount"]
#     return total


class ReportBuilder:
    """Builds a plain-text report from summarized records."""

    def __init__(self, title):
        self.title = title

    def build(self, summary):
        header = f"== {self.title} =="
        body = f"count={summary['count']} total={summary['total']}"
        return header + "\n" + body
