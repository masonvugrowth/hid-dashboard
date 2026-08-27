"""
Guards that gender reaches GHL as a radio option rather than a dead string.

GHL's write API does not validate a RADIO field against its picklist — sending
"male" returns 200 and stores "male" verbatim. It simply matches no option, so
it never renders as a selection and no filter or workflow keyed on an option
value can find the contact. A gender write that looks fine and segments nothing
is the failure mode these tests exist to prevent.

Cloudbeds sends 'M' / 'F' / 'N/A'; the old code lowercased it, so the value
that would have arrived was "m".
"""
from app.services.ghl_crm_service import (
    GENDER_OPTIONS,
    _build_custom_fields,
    _main_guest_gender,
    _normalize_gender,
)

MALE = GENDER_OPTIONS["M"]
FEMALE = GENDER_OPTIONS["F"]


class TestGenderOptions:
    def test_options_are_the_full_picklist_strings(self):
        # Only the exact option string matches. "Male" alone does not, and a
        # test that accepted it would pass while GHL segmented nothing.
        assert MALE.startswith("Male | ")
        assert FEMALE.startswith("Female | ")

    def test_male_and_female_are_distinct(self):
        assert MALE != FEMALE


class TestNormalizeGender:
    def test_cloudbeds_single_letters_map_to_options(self):
        assert _normalize_gender("M") == MALE
        assert _normalize_gender("F") == FEMALE

    def test_lowercase_and_padded_input_still_maps(self):
        assert _normalize_gender(" m ") == MALE
        assert _normalize_gender("f") == FEMALE

    def test_spelled_out_values_map_too(self):
        assert _normalize_gender("Male") == MALE
        assert _normalize_gender("female") == FEMALE

    def test_female_is_not_swallowed_by_the_male_prefix(self):
        # "FEMALE".startswith("MALE") is False, but the check order still has to
        # be right — getting this wrong silently mislabels every woman.
        assert _normalize_gender("FEMALE") == FEMALE

    def test_not_available_is_skipped_not_recorded_as_a_refusal(self):
        # 'N/A' means the property never collected it, which is not the guest
        # choosing "Prefer not to say".
        assert _normalize_gender("N/A") == ""
        assert _normalize_gender("NA") == ""

    def test_unknown_values_are_dropped_rather_than_stored_raw(self):
        # Storing an unmatched string is what this whole fix is about.
        assert _normalize_gender("unspecified") == ""
        assert _normalize_gender("x") == ""

    def test_empty_input(self):
        assert _normalize_gender("") == ""
        assert _normalize_gender(None) == ""


class TestMainGuestGender:
    def test_reads_the_guest_list(self):
        reservation = {"guestList": {"1": {"guestGender": "F"}}}
        assert _main_guest_gender(reservation) == FEMALE

    def test_main_guest_wins_over_dict_order(self):
        # A couple's booking would otherwise report the companion's gender,
        # because guestList order is not guaranteed to put the main guest first.
        reservation = {
            "guestList": {
                "9": {"guestGender": "M"},
                "1": {"guestGender": "F", "isMainGuest": True},
            }
        }
        assert _main_guest_gender(reservation) == FEMALE

    def test_falls_through_to_a_companion_when_the_main_guest_has_none(self):
        reservation = {
            "guestList": {
                "1": {"guestGender": "N/A", "isMainGuest": True},
                "2": {"guestGender": "M"},
            }
        }
        assert _main_guest_gender(reservation) == MALE

    def test_no_guest_list_is_empty_not_an_error(self):
        assert _main_guest_gender({}) == ""
        assert _main_guest_gender({"guestList": []}) == ""
        assert _main_guest_gender({"guestList": {"1": "not-a-dict"}}) == ""


class TestGenderInPayload:
    def test_gender_is_sent_as_the_option_string(self):
        reservation = {
            "reservationID": "6008449404616",
            "guestList": {"1": {"guestGender": "M", "isMainGuest": True}},
        }
        by_key = {f["key"]: f for f in _build_custom_fields(reservation)}
        assert by_key["gender"]["fieldValue"] == MALE

    def test_missing_gender_leaves_the_field_out_entirely(self):
        reservation = {
            "reservationID": "6008449404616",
            "guestList": {"1": {"guestGender": "N/A"}},
        }
        keys = {f["key"] for f in _build_custom_fields(reservation)}
        assert "gender" not in keys
