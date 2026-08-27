"""
Guards that the reservation data actually reaches GHL's custom fields.

For a long stretch every Oani contact came out of the fan-out with names and
phone set and `customFields: []` — 963 booking.com contacts and not one of them
carrying a reservation number. The upsert reported success the whole time,
because a contact write succeeds on the standard fields alone.

Two things caused it, and both are silent: the field-ID lookup that failed
without raising, and GHL accepting a prefixed field key with a 200 while
writing nothing.
"""
from app.services.ghl_crm_service import (
    FIELD_KEY_MAP,
    _build_custom_fields,
    _custom_field_key,
    _get_room_type_short,
)


RESERVATION = {
    "reservationID": "6008449404616",
    "dateCreated": "2026-08-27 11:51:37",
    "startDate": "2026-10-01",
    "endDate": "2026-10-03",
    "status": "confirmed",
    "source": "booking.com",
    "assigned": {"1": {"roomTypeName": "4 Beds Mixed Dormitory"}},
}


class TestCustomFieldKey:
    def test_contact_prefix_is_stripped(self):
        # GHL reports "contact.roomtypename" and accepts only "roomtypename".
        # Sending the prefixed form back returns 200 and writes nothing, which
        # is indistinguishable from success from the caller's side.
        assert _custom_field_key("contact.roomtypename") == "roomtypename"
        assert _custom_field_key("contact.reservation_number") == "reservation_number"

    def test_unprefixed_key_is_left_alone(self):
        assert _custom_field_key("roomtypename") == "roomtypename"

    def test_only_the_first_segment_is_removed(self):
        assert _custom_field_key("contact.a.b") == "a.b"

    def test_every_mapped_key_survives_the_strip(self):
        for field_key in FIELD_KEY_MAP:
            assert _custom_field_key(field_key)
            assert not _custom_field_key(field_key).startswith("contact.")


class TestBuildCustomFields:
    def test_reservation_number_is_always_sent(self):
        fields = _build_custom_fields(RESERVATION, {})
        by_key = {f["key"]: f for f in fields}
        assert by_key["reservation_number"]["fieldValue"] == "6008449404616"

    def test_fields_are_addressed_by_key_never_by_id(self):
        # Addressing by ID required a per-reservation
        # GET /locations/{id}/customFields, and that lookup failing was what
        # emptied the array in the first place.
        for field in _build_custom_fields(RESERVATION, {}):
            assert "key" in field
            assert "id" not in field

    def test_both_value_spellings_are_sent(self):
        # fieldValue is current, field_value is the older documented name.
        # Sending one only is how a rename turns into another silent no-op.
        for field in _build_custom_fields(RESERVATION, {}):
            assert field["fieldValue"] == field["field_value"]

    def test_room_type_reaches_the_payload(self):
        by_key = {f["key"]: f for f in _build_custom_fields(RESERVATION, {})}
        assert by_key["roomtypename"]["fieldValue"] == "4 Beds Mixed Dormitory"

    def test_empty_values_are_dropped_not_sent_blank(self):
        # Blanking a field GHL already holds is worse than leaving it alone.
        sparse = {"reservationID": "999", "source": "", "status": ""}
        keys = {f["key"] for f in _build_custom_fields(sparse, {})}
        assert keys == {"reservation_number"}

    def test_a_reservation_with_no_data_sends_nothing(self):
        assert _build_custom_fields({}, {}) == []


class TestRoomTypeExtraction:
    def test_reads_assigned_rooms(self):
        assert _get_room_type_short(RESERVATION) == "4 Beds Mixed Dormitory"

    def test_short_name_wins_when_both_are_present(self):
        reservation = {
            "assigned": {"1": {
                "roomTypeName": "8 Beds Mixed Dormitory (CRM_June 2026 Events)",
                "roomTypeNameShort": "8 Bed Mixed",
            }}
        }
        assert _get_room_type_short(reservation) == "8 Bed Mixed"

    def test_falls_back_to_unassigned_rooms(self):
        # The room type is picked at booking; the room itself is often assigned
        # on arrival. Reading only `assigned` left the field blank for most
        # future bookings — which is nearly all of them at fan-out time.
        reservation = {
            "assigned": {},
            "unassigned": {"1": {"roomTypeName": "Private Double"}},
        }
        assert _get_room_type_short(reservation) == "Private Double"

    def test_handles_list_shaped_room_collections(self):
        reservation = {"unassigned": [{"roomTypeName": "Private Twin"}]}
        assert _get_room_type_short(reservation) == "Private Twin"

    def test_no_rooms_yields_none_rather_than_raising(self):
        assert _get_room_type_short({}) is None
        assert _get_room_type_short({"assigned": None, "unassigned": ""}) is None
