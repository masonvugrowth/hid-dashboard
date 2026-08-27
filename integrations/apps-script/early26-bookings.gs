/**
 * EARLY26 booking puller — HiD → Google Sheets, one tab per branch.
 *
 * Pulls every reservation whose rate plan is "EARLY26 2 NIGHTS" or
 * "EARLY26 3+ NIGHTS" from the HiD public API and writes it to a sheet
 * named after the branch. Runs on a daily trigger by default; a 30-minute
 * option is one menu click away (see "How fresh is the data?" below).
 *
 * Each run is a full re-pull, upserted by reservation number:
 *   - new booking   -> appended at the bottom of its branch tab
 *   - known booking -> its row is updated in place (status, dates, totals),
 *                      so a cancellation shows up as Status = canceled
 *                      instead of silently disappearing
 * Columns the team adds by hand (notes, owner, follow-up...) are preserved —
 * the script only writes the columns it owns, matched by header name.
 *
 * -- Setup ------------------------------------------------------------------
 * 1. Extensions -> Apps Script, paste this file.
 * 2. Project Settings -> Script Properties, add:
 *      HID_API_URL = https://meander-hid-dashboard.zeabur.app
 *      HID_API_KEY = hid_xxxxxxxx   (HiD -> Settings -> API Keys -> create)
 * 3. Reload the sheet, then menu "EARLY26" -> "Sync now" (approve the
 *    permission prompt once), then "EARLY26" -> "Install daily trigger".
 *
 * -- How fresh is the data? --------------------------------------------------
 * HiD pulls reservations from Cloudbeds on two schedules: a daily
 * modified-7d sync at 02:00 ICT (cron-cloudbeds-modified.yml) and, every
 * 30 min, an incremental sync of the branches covered by an active rate
 * plan quota (cron-rate-plan-quota.yml) — which is exactly the EARLY26
 * branches. So these rows are never more than ~30 min stale upstream;
 * a daily pull is a choice about how often the sheet moves, not a limit.
 * Switch with the menu: daily (default) or every 30 min.
 */

// -- Config ------------------------------------------------------------------

/** Rate plans to pull. Matched as "contains", case-insensitive, against
 *  rate_plan_name OR room_type — same rule the Rate Plan Quota page counts by
 *  (Cloudbeds sometimes packs the tag into room_type). Add a line to extend. */
var RATE_PLANS = [
  'EARLY26 2 NIGHTS',
  'EARLY26 3+ NIGHTS',
];

/** Columns written by the script, in order. `key` is the API field name.
 *  Rename a `header` here and on the sheet together — matching is by text. */
var COLUMNS = [
  { header: 'Reservation #', key: 'reservation_number' },
  { header: 'Status',        key: 'status' },
  { header: 'Branch',        key: 'branch' },
  { header: 'Rate Plan',     key: 'rate_plan_name' },
  { header: 'Room Type',     key: 'room_type' },
  { header: 'Room #',        key: 'room_number' },
  { header: 'Guest Name',    key: 'name' },
  { header: 'Email',         key: 'email' },
  { header: 'Phone',         key: 'phone_number' },
  { header: 'Mobile',        key: 'mobile' },
  { header: 'Country',       key: 'country' },
  { header: 'Gender',        key: 'gender' },
  { header: 'Date of Birth', key: 'date_of_birth' },
  { header: 'Adults',        key: 'adults' },
  { header: 'Children',      key: 'children' },
  { header: 'Check-in',      key: 'check_in_date' },
  { header: 'Check-out',     key: 'check_out_date' },
  { header: 'Nights',        key: 'nights' },
  { header: 'Booked On',     key: 'reservation_date' },
  { header: 'Source',        key: 'source' },
  { header: 'Grand Total',   key: 'grand_total' },
  { header: 'Amount Paid',   key: 'amount_paid' },
  { header: 'Balance Due',   key: 'balance_due' },
  { header: 'Deposit',       key: 'deposit' },
  { header: 'Meal Plan',     key: 'meal_plan' },
  { header: 'OTA Conf #',    key: 'third_party_confirmation_number' },
  { header: 'Canceled On',   key: 'cancellation_date' },
  { header: 'Last Synced',   key: '_synced_at' },
];

/** Hour of day (0-23, spreadsheet timezone) for the daily trigger. Apps
 *  Script fires somewhere inside that hour, not exactly on the dot. 8 = after
 *  the 02:00 ICT Cloudbeds sync, in time for the morning. */
var DAILY_SYNC_HOUR = 8;

var KEY_HEADER = 'Reservation #';
var PAGE_SIZE = 500;      // API caps at 1000
var MAX_PAGES = 40;       // hard stop; 40 * 500 = 20k rows

// -- Menu --------------------------------------------------------------------

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('EARLY26')
    .addItem('Sync now', 'syncEarly26Bookings')
    .addItem('Install daily trigger', 'installDailyTrigger')
    .addItem('Install 30-min trigger', 'installHalfHourlyTrigger')
    .addItem('Remove trigger', 'removeTrigger')
    .addToUi();
}

/** Once a day, around DAILY_SYNC_HOUR. Both installers clear the existing
 *  trigger first, so switching cadence never leaves two running. */
function installDailyTrigger() {
  removeTrigger();
  ScriptApp.newTrigger('syncEarly26Bookings')
    .timeBased()
    .everyDays(1)
    .atHour(DAILY_SYNC_HOUR)
    .create();
  SpreadsheetApp.getActive().toast(
    'Trigger installed — syncing daily around ' + DAILY_SYNC_HOUR + ':00.'
  );
}

/** Matches the upstream rate-plan-quota cron, for when someone is watching
 *  the cap fill up in near-real time. */
function installHalfHourlyTrigger() {
  removeTrigger();
  ScriptApp.newTrigger('syncEarly26Bookings')
    .timeBased()
    .everyMinutes(30)
    .create();
  SpreadsheetApp.getActive().toast('Trigger installed — syncing every 30 min.');
}

function removeTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'syncEarly26Bookings') {
      ScriptApp.deleteTrigger(t);
    }
  });
}

// -- Main --------------------------------------------------------------------

function syncEarly26Bookings() {
  var reservations = fetchReservations_();
  var byBranch = groupBy_(reservations, function (r) {
    return r.branch || 'Unknown branch';
  });

  var syncedAt = Utilities.formatDate(
    new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm'
  );
  var ss = SpreadsheetApp.getActive();
  var summary = [];

  Object.keys(byBranch).sort().forEach(function (branch) {
    var rows = byBranch[branch];
    rows.forEach(function (r) { r._synced_at = syncedAt; });
    var result = writeBranchSheet_(ss, branch, rows);
    summary.push(branch + ': ' + result.added + ' new, ' + result.updated + ' updated');
  });

  var msg = reservations.length + ' bookings — ' + (summary.join(' | ') || 'no matches');
  Logger.log(msg);
  try {
    ss.toast(msg, 'EARLY26 sync', 10);
  } catch (e) {
    // toast() is unavailable on time-based triggers — the log is enough there.
  }
  return msg;
}

// -- API ---------------------------------------------------------------------

function fetchReservations_() {
  var props = PropertiesService.getScriptProperties();
  var base = (props.getProperty('HID_API_URL') || '').replace(/\/+$/, '');
  var key = props.getProperty('HID_API_KEY');
  if (!base || !key) {
    throw new Error(
      'Missing Script Properties. Set HID_API_URL and HID_API_KEY under ' +
      'Project Settings -> Script Properties.'
    );
  }

  var planQuery = RATE_PLANS.map(function (p) {
    return 'rate_plan=' + encodeURIComponent(p);
  }).join('&');

  var all = [];
  for (var page = 0; page < MAX_PAGES; page++) {
    var url = base + '/api/public/reservations?' + planQuery +
      '&limit=' + PAGE_SIZE + '&offset=' + (page * PAGE_SIZE);

    var res = UrlFetchApp.fetch(url, {
      method: 'get',
      headers: { 'X-API-Key': key },
      muteHttpExceptions: true,
    });

    var code = res.getResponseCode();
    var body = res.getContentText();
    if (code !== 200) {
      throw new Error('HiD API ' + code + ' — ' + body.slice(0, 500));
    }

    var parsed = JSON.parse(body);
    if (!parsed.success) {
      throw new Error('HiD API error — ' + (parsed.error || body.slice(0, 500)));
    }

    var batch = (parsed.data && parsed.data.reservations) || [];
    all = all.concat(batch);
    if (batch.length < PAGE_SIZE) {
      return all;
    }
  }
  throw new Error(
    'Stopped at ' + all.length + ' rows (MAX_PAGES hit) — raise MAX_PAGES.'
  );
}

// -- Sheet writing -----------------------------------------------------------

/**
 * Upsert `rows` into the tab named `branch`, keyed on reservation number.
 * Only the columns listed in COLUMNS are touched; anything else on the row
 * (manual notes, formulas) is read back and written unchanged.
 */
function writeBranchSheet_(ss, branch, rows) {
  var name = String(branch).slice(0, 99);
  var sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
  }

  // Header row — created on first run, respected afterwards so a team member
  // can reorder columns or insert their own without the script fighting them.
  var headers = sheet.getLastRow() > 0
    ? sheet.getRange(1, 1, 1, Math.max(sheet.getLastColumn(), 1))
        .getValues()[0].map(String)
    : [];
  if (headers.join('').trim() === '') {
    headers = COLUMNS.map(function (c) { return c.header; });
    sheet.getRange(1, 1, 1, headers.length)
      .setValues([headers])
      .setFontWeight('bold');
    sheet.setFrozenRows(1);
  } else {
    // Append any COLUMNS header the sheet doesn't have yet (e.g. after an
    // upgrade that adds a field) instead of silently dropping the data.
    COLUMNS.forEach(function (c) {
      if (headers.indexOf(c.header) === -1) {
        headers.push(c.header);
        sheet.getRange(1, headers.length).setValue(c.header).setFontWeight('bold');
      }
    });
  }

  var keyIdx = headers.indexOf(KEY_HEADER);
  if (keyIdx === -1) {
    throw new Error(
      'Sheet "' + name + '" has no "' + KEY_HEADER + '" column — ' +
      'rename it back or delete the tab and re-sync.'
    );
  }

  var width = headers.length;
  var lastRow = sheet.getLastRow();
  var existing = lastRow > 1
    ? sheet.getRange(2, 1, lastRow - 1, width).getValues()
    : [];

  var rowByKey = {};
  existing.forEach(function (r, i) {
    var k = String(r[keyIdx] || '').trim();
    if (k) { rowByKey[k] = i; }
  });

  var appended = [];
  var touched = 0;
  rows.forEach(function (r) {
    var k = String(r.reservation_number || '').trim();
    if (!k) { return; }
    if (Object.prototype.hasOwnProperty.call(rowByKey, k)) {
      var i = rowByKey[k];
      existing[i] = mergeRow_(existing[i], headers, r);
      touched++;
    } else {
      appended.push(mergeRow_(blankRow_(width), headers, r));
      rowByKey[k] = -1;   // guard against a duplicate id inside one payload
    }
  });

  if (existing.length) {
    sheet.getRange(2, 1, existing.length, width).setValues(existing);
  }
  if (appended.length) {
    sheet.getRange(existing.length + 2, 1, appended.length, width)
      .setValues(appended);
  }

  return { updated: touched, added: appended.length };
}

/** Copy the API values onto a sheet row, leaving unmanaged columns as-is. */
function mergeRow_(row, headers, api) {
  var out = row.slice();
  while (out.length < headers.length) { out.push(''); }
  COLUMNS.forEach(function (c) {
    var idx = headers.indexOf(c.header);
    if (idx === -1) { return; }
    var v = api[c.key];
    out[idx] = (v === null || v === undefined) ? '' : v;
  });
  return out;
}

// -- Utils -------------------------------------------------------------------

function blankRow_(width) {
  var row = [];
  for (var i = 0; i < width; i++) { row.push(''); }
  return row;
}

function groupBy_(items, keyFn) {
  var out = {};
  items.forEach(function (it) {
    var k = keyFn(it);
    (out[k] = out[k] || []).push(it);
  });
  return out;
}
