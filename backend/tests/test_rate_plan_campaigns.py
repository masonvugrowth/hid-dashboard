"""Hand-typed rate plan → campaign labels on the CRM Reservations table.

Two things matter here. First, the deploy window: Zeabur does not run Alembic
on deploy, so between this landing and `POST /api/sync/run-migrations` the
table does not exist — and the CRM tab reads it on every request. Second, the
label is only ever what a human typed, so a blank must clear the row rather
than store an empty string that reads as "campaign: (nothing)".
"""
import pytest

from app.routers.marketing_activity import (
    RatePlanCampaignIn,
    get_rate_plan_campaigns,
    upsert_rate_plan_campaign,
)
from app.services.rate_plan_campaigns import (
    apply_campaign_labels,
    campaign_map as _campaign_map,
    label_rows,
)


class _Row:
    def __init__(self, rate_plan_name, campaign_name):
        self.rate_plan_name = rate_plan_name
        self.campaign_name = campaign_name


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    """Just enough Session for the campaign-label endpoints."""

    def __init__(self, rows=(), raises=False):
        self._rows = list(rows)
        self._raises = raises
        self.rolled_back = False
        self.added = []
        self.deleted = []
        self.commits = 0

    def query(self, *a, **k):
        if self._raises:
            raise RuntimeError('relation "rate_plan_campaigns" does not exist')
        return _FakeQuery(self._rows)

    def rollback(self):
        self.rolled_back = True

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def commit(self):
        self.commits += 1


class TestMissingTableIsContained:
    def test_map_is_empty_instead_of_raising(self):
        assert _campaign_map(_FakeSession(raises=True)) == {}

    def test_and_rolls_the_session_back(self):
        """A failed statement poisons the transaction; without a rollback the
        rest of the CRM tab's queries fail too."""
        db = _FakeSession(raises=True)
        _campaign_map(db)
        assert db.rolled_back is True

    def test_endpoint_still_answers(self):
        body = get_rate_plan_campaigns(db=_FakeSession(raises=True))
        assert body["success"] is True
        assert body["data"] == {}


class TestReading:
    def test_returns_a_flat_map(self):
        db = _FakeSession([
            _Row("WELCOME BACK", "Returning Guest 2026"),
            _Row("CRM_August 2026 Events", "August Events"),
        ])
        assert _campaign_map(db) == {
            "WELCOME BACK": "Returning Guest 2026",
            "CRM_August 2026 Events": "August Events",
        }


class TestWriting:
    def test_creates_a_row_when_none_exists(self):
        db = _FakeSession([])
        body = upsert_rate_plan_campaign(
            RatePlanCampaignIn(rate_plan_name="WELCOME", campaign_name="Welcome Flow"),
            db=db,
        )
        assert len(db.added) == 1
        assert db.added[0].rate_plan_name == "WELCOME"
        assert db.added[0].campaign_name == "Welcome Flow"
        assert db.commits == 1
        assert body["data"]["campaign_name"] == "Welcome Flow"

    def test_updates_the_existing_row_in_place(self):
        row = _Row("WELCOME", "Old Name")
        db = _FakeSession([row])
        upsert_rate_plan_campaign(
            RatePlanCampaignIn(rate_plan_name="WELCOME", campaign_name="New Name"),
            db=db,
        )
        assert row.campaign_name == "New Name"
        assert db.added == []
        assert db.commits == 1

    def test_blank_deletes_the_row(self):
        row = _Row("WELCOME", "Welcome Flow")
        db = _FakeSession([row])
        body = upsert_rate_plan_campaign(
            RatePlanCampaignIn(rate_plan_name="WELCOME", campaign_name="   "),
            db=db,
        )
        assert db.deleted == [row]
        assert body["data"]["campaign_name"] is None

    def test_blank_on_an_untagged_plan_is_a_no_op(self):
        db = _FakeSession([])
        upsert_rate_plan_campaign(
            RatePlanCampaignIn(rate_plan_name="WELCOME", campaign_name=""),
            db=db,
        )
        assert db.deleted == [] and db.added == [] and db.commits == 0

    def test_whitespace_is_trimmed_off_both_fields(self):
        db = _FakeSession([])
        upsert_rate_plan_campaign(
            RatePlanCampaignIn(rate_plan_name="  WELCOME  ",
                               campaign_name="  Welcome Flow  "),
            db=db,
        )
        assert db.added[0].rate_plan_name == "WELCOME"
        assert db.added[0].campaign_name == "Welcome Flow"

    def test_a_whitespace_only_rate_plan_is_rejected(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            upsert_rate_plan_campaign(
                RatePlanCampaignIn(rate_plan_name="   ", campaign_name="X"),
                db=_FakeSession([]),
            )
        assert exc.value.status_code == 400


class TestReportLabels:
    """Reports show the campaign the team typed; anything unlabelled keeps
    its rate plan name so a half-filled table still reads."""

    CMAP = {"WELCOME BACK": "Returning Guest 2026"}

    def test_a_labelled_row_renders_as_the_campaign(self):
        rows = [{"rate_plan_name": "WELCOME BACK", "label": "WELCOME BACK"}]
        label_rows(rows, self.CMAP)
        assert rows[0]["label"] == "Returning Guest 2026"
        assert rows[0]["campaign_name"] == "Returning Guest 2026"

    def test_an_unlabelled_row_keeps_its_rate_plan_name(self):
        rows = [{"rate_plan_name": "WELCOME", "label": "WELCOME"}]
        label_rows(rows, self.CMAP)
        assert rows[0]["label"] == "WELCOME"
        assert rows[0]["campaign_name"] is None

    def test_the_rate_plan_name_is_never_rewritten(self):
        """It is the join key for prior/year-ago rows and the anchor for
        comment and flag-override keys — relabelling must not move it."""
        rows = [{"rate_plan_name": "WELCOME BACK", "label": "WELCOME BACK"}]
        label_rows(rows, self.CMAP)
        assert rows[0]["rate_plan_name"] == "WELCOME BACK"

    def test_a_row_with_no_label_yet_gets_one(self):
        rows = [{"rate_plan_name": "WELCOME"}]
        label_rows(rows, self.CMAP)
        assert rows[0]["label"] == "WELCOME"

    def test_biweekly_payload_shape(self):
        payload = [{"crm": {"by_rate_plan": [
            {"rate_plan_name": "WELCOME BACK", "label": "WELCOME BACK"},
        ]}}]
        apply_campaign_labels(_FakeSession([_Row("WELCOME BACK", "Returning Guest 2026")]),
                              payload)
        assert payload[0]["crm"]["by_rate_plan"][0]["label"] == "Returning Guest 2026"

    def test_weekly_payload_shape(self):
        payload = [{"analytics": {"crm": {"by_rate_plan": [
            {"rate_plan_name": "WELCOME BACK", "label": "WELCOME BACK"},
        ]}}}]
        apply_campaign_labels(_FakeSession([_Row("WELCOME BACK", "Returning Guest 2026")]),
                              payload)
        assert (payload[0]["analytics"]["crm"]["by_rate_plan"][0]["label"]
                == "Returning Guest 2026")

    def test_a_payload_with_no_crm_section_is_left_alone(self):
        payload = [{"branch_name": "MEANDER Saigon"}]
        apply_campaign_labels(_FakeSession([_Row("WELCOME BACK", "X")]), payload)
        assert payload == [{"branch_name": "MEANDER Saigon"}]

    def test_a_missing_table_leaves_the_report_untouched(self):
        payload = [{"crm": {"by_rate_plan": [
            {"rate_plan_name": "WELCOME BACK", "label": "WELCOME BACK"},
        ]}}]
        apply_campaign_labels(_FakeSession(raises=True), payload)
        assert payload[0]["crm"]["by_rate_plan"][0]["label"] == "WELCOME BACK"
