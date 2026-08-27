"""
Guards for the Cloudbeds push (realtime) path and the dedup ordering it relies on.

The fan-out has exactly one shot per reservation, so the two things that must
never regress are: a reservation is not written off as "seen" before it has
actually been fanned out, and the push endpoint does not accept unsigned bodies.
"""
import hashlib
import hmac
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.routers import webhooks


# ── Dedup ordering ───────────────────────────────────────────────────────────

class TestSeenOrdering:
    """A reservation earns the seen mark by being fanned out, not by being read.

    Marking on the way in meant a Cloudbeds fetch that timed out took the
    reservation out of the running for the rest of the process's life: the
    in-process seen cache said "done", the poller skipped it on every later
    pass, and the conversion was never uploaded.
    """

    def test_failed_fetch_leaves_reservation_unseen(self):
        with patch.object(webhooks.webhook_log, "has_seen", return_value=False), \
             patch.object(webhooks, "_fetch_full_reservation", return_value=None), \
             patch.object(webhooks, "_fan_out") as fan_out, \
             patch.object(webhooks.webhook_log, "mark_seen") as mark_seen:
            webhooks._process_reservation("12345", "999")

        fan_out.assert_not_called()
        mark_seen.assert_not_called()

    def test_successful_fan_out_marks_seen(self):
        with patch.object(webhooks.webhook_log, "has_seen", return_value=False), \
             patch.object(webhooks, "_fetch_full_reservation", return_value={"reservationID": "999"}), \
             patch.object(webhooks, "_fan_out") as fan_out, \
             patch.object(webhooks.webhook_log, "mark_seen") as mark_seen:
            webhooks._process_reservation("12345", "999")

        fan_out.assert_called_once()
        mark_seen.assert_called_once_with("999")

    def test_already_seen_reservation_is_not_fanned_out_again(self):
        # A poll can reach the same reservation while a push event is still
        # waiting out its settle delay. Whichever gets there second must stop.
        with patch.object(webhooks.webhook_log, "has_seen", return_value=True), \
             patch.object(webhooks, "_fetch_full_reservation") as fetch, \
             patch.object(webhooks, "_fan_out") as fan_out:
            webhooks._process_reservation("12345", "999")

        fetch.assert_not_called()
        fan_out.assert_not_called()


# ── Signature ────────────────────────────────────────────────────────────────

class TestVerifySignature:
    BODY = b'{"reservationID":"999"}'

    def _sign(self, secret: str) -> str:
        return hmac.new(secret.encode(), self.BODY, hashlib.sha256).hexdigest()

    def test_no_secret_configured_rejects(self):
        # Used to return True — an endpoint that fans out to four ad platforms
        # accepting anything from anyone who found the URL.
        with patch.object(webhooks.settings, "CLOUDBEDS_WEBHOOK_SECRET", ""):
            assert webhooks._verify_signature(self.BODY, "sha256=whatever") is False

    def test_missing_signature_rejects(self):
        with patch.object(webhooks.settings, "CLOUDBEDS_WEBHOOK_SECRET", "s3cret"):
            assert webhooks._verify_signature(self.BODY, None) is False

    def test_wrong_signature_rejects(self):
        with patch.object(webhooks.settings, "CLOUDBEDS_WEBHOOK_SECRET", "s3cret"):
            assert webhooks._verify_signature(self.BODY, "sha256=" + "0" * 64) is False

    def test_prefixed_and_bare_digests_both_accepted(self):
        with patch.object(webhooks.settings, "CLOUDBEDS_WEBHOOK_SECRET", "s3cret"):
            digest = self._sign("s3cret")
            assert webhooks._verify_signature(self.BODY, f"sha256={digest}") is True
            assert webhooks._verify_signature(self.BODY, digest) is True


# ── Payload parsing ──────────────────────────────────────────────────────────

class TestPayloadId:
    def test_reads_root_level_key(self):
        assert webhooks._payload_id({"reservationID": 999}, "reservationID") == "999"

    def test_falls_back_to_nested_data_object(self):
        payload = {"event": "reservation/created", "data": {"reservationID": "999"}}
        assert webhooks._payload_id(payload, "reservationID") == "999"

    def test_accepts_any_of_the_casing_variants(self):
        payload = {"reservation_id": "999"}
        assert webhooks._payload_id(payload, "reservationID", "reservation_id") == "999"

    def test_missing_id_is_empty_not_an_error(self):
        assert webhooks._payload_id({"data": []}, "reservationID") == ""


# ── Branch routing ───────────────────────────────────────────────────────────

class TestBranchesByMode:
    """WEBHOOK_REALTIME_BRANCHES decides which job covers a branch.

    Every branch must land in exactly one of the two lists — a branch in
    neither stops being processed at all, which is the failure that would be
    hardest to notice from the monitor.
    """

    def _slugs(self, realtime: bool) -> set:
        return {row[0] for row in webhooks._branches_by_mode(realtime)}

    def test_empty_setting_keeps_every_branch_on_polling(self):
        with patch.object(webhooks.settings, "WEBHOOK_REALTIME_BRANCHES", ""):
            assert self._slugs(realtime=False) == {
                "saigon", "taipei", "1948", "oani", "osaka",
            }
            assert self._slugs(realtime=True) == set()

    def test_listed_branch_moves_to_the_safety_net_only(self):
        with patch.object(webhooks.settings, "WEBHOOK_REALTIME_BRANCHES", "oani"):
            assert self._slugs(realtime=True) == {"oani"}
            assert "oani" not in self._slugs(realtime=False)

    def test_setting_is_split_trimmed_and_lowercased(self):
        with patch.object(webhooks.settings, "WEBHOOK_REALTIME_BRANCHES", " Oani , OSAKA "):
            assert self._slugs(realtime=True) == {"oani", "osaka"}

    def test_no_branch_falls_between_the_two_jobs(self):
        with patch.object(webhooks.settings, "WEBHOOK_REALTIME_BRANCHES", "oani,saigon"):
            covered = self._slugs(realtime=True) | self._slugs(realtime=False)
            assert covered == {"saigon", "taipei", "1948", "oani", "osaka"}


# ── Endpoint ─────────────────────────────────────────────────────────────────

class FakeRequest:
    def __init__(self, body: bytes):
        self._body = body

    async def body(self) -> bytes:
        return self._body

    async def json(self):
        import json
        return json.loads(self._body)


class FakeBackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, fn, *args):
        self.tasks.append((fn, args))


@pytest.mark.asyncio
class TestCloudbedsWebhookEndpoint:
    SECRET = "s3cret"

    def _signed(self, body: bytes) -> str:
        return "sha256=" + hmac.new(self.SECRET.encode(), body, hashlib.sha256).hexdigest()

    async def test_unsigned_request_is_rejected(self):
        body = b'{"propertyID":"1","reservationID":"999"}'
        with patch.object(webhooks.settings, "CLOUDBEDS_WEBHOOK_SECRET", self.SECRET):
            with pytest.raises(HTTPException) as exc:
                await webhooks.cloudbeds_webhook(FakeRequest(body), FakeBackgroundTasks(), None)
        assert exc.value.status_code == 401

    async def test_valid_push_is_queued_with_the_settle_delay(self):
        body = b'{"propertyID":"1","reservationID":"999"}'
        run_at = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
        with patch.object(webhooks.settings, "CLOUDBEDS_WEBHOOK_SECRET", self.SECRET), \
             patch.object(webhooks.webhook_log, "has_seen", return_value=False), \
             patch.object(webhooks, "_queue_fan_out", return_value=run_at) as queue:
            result = await webhooks.cloudbeds_webhook(
                FakeRequest(body), FakeBackgroundTasks(), self._signed(body)
            )

        queue.assert_called_once_with("1", "999")
        assert result["success"] is True

    async def test_without_a_scheduler_it_falls_back_to_immediate_processing(self):
        # Losing the settle delay is worse than losing the reservation, so the
        # fallback still runs rather than dropping the event.
        body = b'{"propertyID":"1","reservationID":"999"}'
        background = FakeBackgroundTasks()
        with patch.object(webhooks.settings, "CLOUDBEDS_WEBHOOK_SECRET", self.SECRET), \
             patch.object(webhooks.webhook_log, "has_seen", return_value=False), \
             patch.object(webhooks, "_queue_fan_out", return_value=None):
            await webhooks.cloudbeds_webhook(FakeRequest(body), background, self._signed(body))

        assert background.tasks == [(webhooks._process_reservation, ("1", "999"))]

    async def test_duplicate_push_is_acknowledged_without_re_processing(self):
        body = b'{"propertyID":"1","reservationID":"999"}'
        with patch.object(webhooks.settings, "CLOUDBEDS_WEBHOOK_SECRET", self.SECRET), \
             patch.object(webhooks.webhook_log, "has_seen", return_value=True), \
             patch.object(webhooks, "_queue_fan_out") as queue:
            result = await webhooks.cloudbeds_webhook(
                FakeRequest(body), FakeBackgroundTasks(), self._signed(body)
            )

        queue.assert_not_called()
        assert result["message"] == "already processed"

    async def test_payload_without_ids_is_acknowledged_not_retried(self):
        # A 4xx would make Cloudbeds retry a payload that will never carry IDs.
        body = b'{"event":"ping"}'
        with patch.object(webhooks.settings, "CLOUDBEDS_WEBHOOK_SECRET", self.SECRET), \
             patch.object(webhooks, "_queue_fan_out") as queue:
            result = await webhooks.cloudbeds_webhook(
                FakeRequest(body), FakeBackgroundTasks(), self._signed(body)
            )

        queue.assert_not_called()
        assert result["success"] is True
