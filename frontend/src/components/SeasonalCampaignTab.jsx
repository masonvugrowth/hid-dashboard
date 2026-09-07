/**
 * Marketing Activity → Seasonal Campaign.
 *
 * A seasonal push is bought through ads and sold through a rate plan, so the
 * table puts both sides on one row: what the ad platform spent and could
 * attribute, next to what actually booked on the rate plan. The two never
 * agree — ad matching misses the guest who saw the ad Tuesday and phoned in
 * Friday — and showing the gap is the point.
 *
 * Set-up is two lists of names the team types once (ad campaign, rate plan)
 * plus the campaign's cost %, which is charged against ACTUAL revenue.
 */
import { useRef, useState } from "react";
import { useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import {
  getSeasonalCampaigns,
  getSeasonalCampaignPerformance,
  createSeasonalCampaign,
  updateSeasonalCampaign,
  deleteSeasonalCampaign,
} from "../api/marketingActivity";

function fmtNum(val) {
  if (val == null) return "—";
  return new Intl.NumberFormat("en").format(Math.round(val));
}

function RoasBadge({ value }) {
  if (value == null) return <span className="text-gray-400">—</span>;
  const cls =
    value >= 3 ? "text-green-700 bg-green-50"
    : value >= 1.5 ? "text-yellow-700 bg-yellow-50"
    : "text-red-600 bg-red-50";
  return (
    <span className={"px-2 py-0.5 rounded text-xs font-semibold " + cls}>
      {value.toFixed(2)}x
    </span>
  );
}

/* Cost % edited in place — the one number on this row a human tunes, and the
 * one they tune repeatedly while a campaign is running. Making them reopen
 * the set-up dialog for it turns a two-second correction into six clicks.
 * Same click-to-edit shape as the Campaign cell on the CRM tab. */
function CostPctCell({ value, onSave, saving }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const inputRef = useRef(null);

  const start = () => {
    setDraft(String(value ?? 0));
    setEditing(true);
    setTimeout(() => inputRef.current?.select(), 0);
  };

  const commit = () => {
    setEditing(false);
    const next = Number(draft);
    // A typo is not an instruction to set 0% — leave the old value alone.
    if (draft.trim() === "" || Number.isNaN(next)) return;
    const clamped = Math.min(100, Math.max(0, next));
    if (clamped !== Number(value ?? 0)) onSave(clamped);
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        type="number"
        step="0.01"
        min="0"
        max="100"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit();
          if (e.key === "Escape") setEditing(false);
        }}
        className="w-20 text-sm text-right border border-blue-400 rounded px-2 py-1 bg-white outline-none"
      />
    );
  }

  return (
    <button
      onClick={start}
      title="Click to edit — charged on actual revenue"
      className="w-full text-right text-sm rounded px-2 py-1 transition-colors hover:bg-yellow-100"
    >
      {saving ? (
        <span className="text-gray-400">Saving…</span>
      ) : value ? (
        `${value}%`
      ) : (
        <span className="text-gray-300">0%</span>
      )}
    </button>
  );
}

// Names are typed one per line — the same shape they get pasted in from a
// campaign list, and no ambiguity about commas inside a campaign name.
const linesToList = (text) =>
  (text || "").split("\n").map((s) => s.trim()).filter(Boolean);
const listToLines = (list) => (list || []).join("\n");

const EMPTY_FORM = {
  name: "",
  ads: "",
  ratePlans: "",
  costPct: "0",
  notes: "",
  is_active: true,
};

function SetupDialog({ campaign, onClose, onSaved }) {
  const [form, setForm] = useState(
    campaign
      ? {
          name: campaign.name,
          ads: listToLines(campaign.ads_campaign_names),
          ratePlans: listToLines(campaign.rate_plan_names),
          costPct: String(campaign.cost_pct ?? 0),
          notes: campaign.notes || "",
          is_active: campaign.is_active,
        }
      : EMPTY_FORM
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    const body = {
      name: form.name.trim(),
      ads_campaign_names: linesToList(form.ads),
      rate_plan_names: linesToList(form.ratePlans),
      cost_pct: Number(form.costPct) || 0,
      notes: form.notes.trim() || null,
      is_active: form.is_active,
    };
    try {
      if (campaign) await updateSeasonalCampaign(campaign.id, body);
      else await createSeasonalCampaign(body);
      onSaved();
    } catch (err) {
      // Keep the dialog open with what they typed — a closed dialog after a
      // rejected save looks exactly like a successful one.
      setError(err?.response?.data?.detail || err?.message || "Could not save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <form
        onSubmit={submit}
        className="bg-white rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto"
      >
        <div className="px-5 py-4 border-b">
          <h3 className="font-semibold text-gray-900">
            {campaign ? "Edit campaign" : "New seasonal campaign"}
          </h3>
          <p className="text-xs text-gray-500 mt-1">
            Names match as case-insensitive substrings, so a partial tag like{" "}
            <code className="bg-gray-100 px-1 rounded">TET2027</code> catches every
            decorated variant.
          </p>
        </div>

        <div className="px-5 py-4 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">
              Campaign name
            </label>
            <input
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              required
              maxLength={200}
              placeholder="Tet 2027"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">
              Ads campaign name(s) — one per line
            </label>
            <textarea
              value={form.ads}
              onChange={(e) => set("ads", e.target.value)}
              rows={3}
              placeholder={"TET2027\nTet Early Bird"}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
            />
            <p className="text-xs text-gray-400 mt-1">
              Drives Spend, Bookings from Ads and Revenue from Ads.
            </p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">
              Rate Plan Name(s) — one per line
            </label>
            <textarea
              value={form.ratePlans}
              onChange={(e) => set("ratePlans", e.target.value)}
              rows={3}
              placeholder={"TET 2027 Package"}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
            />
            <p className="text-xs text-gray-400 mt-1">
              Drives the real numbers. Matched on Rate Plan Name and Room Type,
              by Date Booked.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">
                Cost % of campaign
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="100"
                  value={form.costPct}
                  onChange={(e) => set("costPct", e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                />
                <span className="text-sm text-gray-500">%</span>
              </div>
              <p className="text-xs text-gray-400 mt-1">
                Charged on actual revenue.
              </p>
            </div>
            <div className="flex items-end pb-2">
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => set("is_active", e.target.checked)}
                />
                Active
              </label>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">
              Notes (optional)
            </label>
            <input
              value={form.notes}
              onChange={(e) => set("notes", e.target.value)}
              maxLength={500}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
              {error}
            </p>
          )}
        </div>

        <div className="px-5 py-4 border-t flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
    </div>
  );
}

export default function SeasonalCampaignTab({ branchId, month, ytd, cur, periodLabel }) {
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState(null); // null | {campaign?: row}
  const [error, setError] = useState(null);
  const [savingPct, setSavingPct] = useState(null);

  const params = {};
  if (branchId) params.branch_id = branchId;
  if (ytd) {
    params.date_from = ytd.date_from;
    params.date_to = ytd.date_to;
  } else {
    params.month = month;
  }

  const { data, isPending, isPlaceholderData } = useQuery({
    queryKey: ["seasonal-campaign-performance", branchId || "all", month, ytd?.date_from, ytd?.date_to],
    queryFn: () => getSeasonalCampaignPerformance(params),
    placeholderData: keepPreviousData,
  });

  // Definitions are fetched separately so the dialog can open on the full
  // record even while the numbers are still loading.
  const { data: definitions } = useQuery({
    queryKey: ["seasonal-campaigns"],
    queryFn: getSeasonalCampaigns,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["seasonal-campaigns"] });
    queryClient.invalidateQueries({ queryKey: ["seasonal-campaign-performance"] });
  };

  const saveCostPct = async (row, pct) => {
    setSavingPct(row.id);
    setError(null);
    try {
      await updateSeasonalCampaign(row.id, { cost_pct: pct });
      refresh();
    } catch (e) {
      // Leave the old % on screen — the cell must never show a value the
      // server didn't accept.
      setError(
        `Could not save the cost % for "${row.name}": ` +
          (e?.response?.data?.detail || e?.message || "unknown error")
      );
    } finally {
      setSavingPct(null);
    }
  };

  const remove = async (row) => {
    if (!window.confirm(`Delete "${row.name}"? The bookings and ad data stay put — only the tracking setup is removed.`)) return;
    setError(null);
    try {
      await deleteSeasonalCampaign(row.id);
      refresh();
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "Could not delete");
    }
  };

  const rows = data?.rows || [];
  const anySpendMissing = rows.some((r) => r.spend == null);
  const unconfigured = (definitions || []).filter(
    (d) => !d.ads_campaign_names?.length && !d.rate_plan_names?.length
  );

  const header = (
    <div className="flex items-start justify-between gap-3 flex-wrap">
      <p className="text-sm text-gray-500 max-w-3xl">
        Each campaign twice over: what the ad platform spent and could attribute back
        to a click, next to what actually booked on the rate plan. Ad matching misses
        the guest who saw the ad and booked later by phone or OTA, so{" "}
        <span className="font-medium text-gray-600">actual</span> is normally the
        larger, and truer, number.
        <br />
        <span className="text-gray-400">
          Both sides cover {periodLabel}, filtered by Date Booked. Spend, Bookings and
          Revenue from Ads all come off the named ad campaign&apos;s own rows. Cost %
          is editable in place and charged on actual revenue; Total Cost adds ad
          spend on top.
        </span>
      </p>
      <button
        onClick={() => setDialog({})}
        className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 whitespace-nowrap"
      >
        + Add campaign
      </button>
    </div>
  );

  if (isPending && !data) {
    return (
      <div className="space-y-4">
        {header}
        <div className="text-center text-gray-400 py-16 text-sm animate-pulse">Loading…</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {header}

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
          {error}
        </p>
      )}

      {anySpendMissing && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
          Ad spend could not be read from the Ads Platform for this period, so Spend
          and ROAS show a dash rather than a zero. The rate-plan columns are unaffected.
        </p>
      )}

      {unconfigured.length > 0 && (
        <p className="text-xs text-gray-500">
          {unconfigured.map((d) => d.name).join(", ")} —{" "}
          {unconfigured.length === 1 ? "has" : "have"} no ad campaign or rate plan name
          set yet, so every column reads zero.
        </p>
      )}

      {rows.length === 0 ? (
        <p className="text-gray-400 text-sm text-center py-12">
          No seasonal campaigns yet. Add one with the ad campaign name and the rate
          plan name it sells on.
        </p>
      ) : (
        <div
          className={
            "bg-white rounded-lg border overflow-x-auto transition-opacity duration-150 " +
            (isPlaceholderData ? "opacity-40 pointer-events-none" : "")
          }
        >
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Campaign</th>
                <th className="text-right px-3 py-3 font-semibold text-gray-600">Spend ({cur})</th>
                <th className="text-right px-3 py-3 font-semibold text-gray-600">Bookings<br /><span className="font-normal text-gray-400">from Ads</span></th>
                <th className="text-right px-3 py-3 font-semibold text-gray-600">Revenue<br /><span className="font-normal text-gray-400">from Ads</span></th>
                <th className="text-right px-3 py-3 font-semibold text-gray-600">ROAS<br /><span className="font-normal text-gray-400">Ads</span></th>
                <th className="text-right px-3 py-3 font-semibold text-gray-600 border-l">Bookings<br /><span className="font-normal text-gray-400">actual</span></th>
                <th className="text-right px-3 py-3 font-semibold text-gray-600">Revenue<br /><span className="font-normal text-gray-400">actual</span></th>
                <th className="text-right px-3 py-3 font-semibold text-gray-600">Cost %</th>
                <th className="text-right px-3 py-3 font-semibold text-gray-600">Campaign<br /><span className="font-normal text-gray-400">cost</span></th>
                <th className="text-right px-3 py-3 font-semibold text-gray-600">Total<br /><span className="font-normal text-gray-400">cost</span></th>
                <th className="text-right px-3 py-3 font-semibold text-gray-600">ROAS<br /><span className="font-normal text-gray-400">actual</span></th>
                <th className="px-3 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map((r) => (
                <tr key={r.id} className={"hover:bg-gray-50 " + (r.is_active ? "" : "opacity-50")}>
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-900">{r.name}</p>
                    <p
                      className="text-xs text-gray-400"
                      title={[
                        `Ads: ${r.ads_campaign_names.join(", ") || "—"}`,
                        `Rate plans: ${r.rate_plan_names.join(", ") || "—"}`,
                        r.ads_source === "booking_matches"
                          ? "Ad columns came from the booking matcher — the ad rows carried no conversion field."
                          : "Ad columns came from this campaign's own ad rows.",
                      ].join("\n")}
                    >
                      {r.matched_ads} ad{r.matched_ads === 1 ? "" : "s"} matched
                      {r.ads_source === "booking_matches" ? " · via matcher" : ""}
                      {r.is_active ? "" : " · inactive"}
                    </p>
                  </td>
                  <td className="px-3 py-3 text-right">{fmtNum(r.spend)}</td>
                  <td className="px-3 py-3 text-right">{fmtNum(r.ads_bookings)}</td>
                  <td className="px-3 py-3 text-right">{fmtNum(r.ads_revenue)}</td>
                  <td className="px-3 py-3 text-right"><RoasBadge value={r.roas_ads} /></td>
                  <td className="px-3 py-3 text-right border-l font-medium">{fmtNum(r.actual_bookings)}</td>
                  <td className="px-3 py-3 text-right font-medium">{fmtNum(r.actual_revenue)}</td>
                  <td className="px-1 py-2">
                    <CostPctCell
                      value={r.cost_pct}
                      saving={savingPct === r.id}
                      onSave={(pct) => saveCostPct(r, pct)}
                    />
                  </td>
                  <td className="px-3 py-3 text-right">{fmtNum(r.campaign_cost)}</td>
                  <td className="px-3 py-3 text-right">{fmtNum(r.total_cost)}</td>
                  <td className="px-3 py-3 text-right"><RoasBadge value={r.roas_actual} /></td>
                  <td className="px-3 py-3 text-right whitespace-nowrap">
                    <button
                      onClick={() =>
                        setDialog({
                          campaign: (definitions || []).find((d) => d.id === r.id) || r,
                        })
                      }
                      className="text-xs text-indigo-600 hover:underline"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => remove(r)}
                      className="text-xs text-gray-400 hover:text-red-600 ml-3"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {dialog && (
        <SetupDialog
          campaign={dialog.campaign}
          onClose={() => setDialog(null)}
          onSaved={() => {
            setDialog(null);
            refresh();
          }}
        />
      )}
    </div>
  );
}
