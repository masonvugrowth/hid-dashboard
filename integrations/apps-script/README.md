# Apps Script integrations

Google Apps Script files that live in a Google Sheet, not on the server.
They are kept here so the code is versioned and reviewable; deploying one
means pasting it into the sheet's script editor.

## early26-bookings.gs

Pulls every reservation on the `EARLY26 2 NIGHTS` / `EARLY26 3+ NIGHTS`
rate plans from the HiD public API and writes one tab per branch
(`MEANDER Saigon`, `MEANDER Osaka`, …), upserted by reservation number.

### Deploy

1. In the target spreadsheet: **Extensions → Apps Script**, paste the file
   contents over `Code.gs`, save.
2. **Project Settings → Script Properties**:
   | Property | Value |
   | --- | --- |
   | `HID_API_URL` | `https://meander-hid-dashboard.zeabur.app` |
   | `HID_API_KEY` | an API key from HiD → Settings → API Keys (shown once) |
3. Reload the spreadsheet → menu **EARLY26 → Sync now** (approve the OAuth
   prompt), then **EARLY26 → Install 30-min trigger**.

### Behaviour

- Full re-pull each run, upsert keyed on reservation number: new bookings are
  appended, known ones updated in place — a cancellation turns into
  `Status = canceled` rather than a vanishing row.
- Columns are matched by header text, so manual columns added to the right
  (notes, owner, follow-up) survive every sync.
- Any non-200 from the API throws, so a broken key or a down backend surfaces
  as an Apps Script failure email instead of a silently stale sheet.

### Adding a rate plan

Edit `RATE_PLANS` at the top of the file. Values are matched as
case-insensitive "contains" against `rate_plan_name` **or** `room_type` —
the same rule the Rate Plan Quotas page counts by, because Cloudbeds
sometimes packs the campaign tag into the room type instead.

### API used

`GET /api/public/reservations` (header `X-API-Key`), with:

| Param | Meaning |
| --- | --- |
| `rate_plan` | repeatable; OR'd together |
| `date_from` / `date_to` + `date_field` | `check_in` (default) or `booked` |
| `modified_since` | ISO timestamp, for incremental pulls (`updated_at`) |
| `branch_id`, `status`, `limit`, `offset` | as before |

Reservation data in HiD refreshes from Cloudbeds on the 30-minute rate-plan
quota job and the 02:00 full sync, so the sheet is at most ~30 minutes behind.
