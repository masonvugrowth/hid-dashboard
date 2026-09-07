/**
 * Row x branch matrix with a per-row heatmap.
 *
 * Shared by Marketing Activity's CRM Reservations and Seasonal Campaign tabs.
 * Both ask the same question — which branch did this land in? — and both can
 * only ask it once every branch is on one currency, so the caller is
 * responsible for handing over figures already normalised to VND.
 */
export function shortBranchName(name) {
  return (name || "").replace(/^meander\s+/i, "").trim() || name || "—";
}

// Per-row heatmap: shade a cell by its share of that row's leading branch.
// Darker indigo = higher within the row, so the winner per campaign/month
// pops out and you can read "hơn thua" at a glance.
export function heatStyle(value, rowMax) {
  if (!value || value <= 0 || rowMax <= 0) return { style: undefined, cls: "text-gray-300" };
  const intensity = value / rowMax;
  const alpha = (0.1 + 0.5 * intensity).toFixed(3);
  const dark = intensity >= 0.65;
  return {
    style: { backgroundColor: `rgba(79,70,229,${alpha})` },
    cls: dark ? "text-white font-semibold" : intensity >= 0.999 ? "text-indigo-900 font-semibold" : "text-gray-700",
  };
}

function defaultFormat(val) {
  if (val == null) return "—";
  return new Intl.NumberFormat("en").format(Math.round(val));
}

/**
 * `rowTitle(row)` names the row; `rowHint(row)` is its hover text.
 * `formatValue` overrides the default thousands-separated integer — a ROAS
 * column wants "3.20x", not "3".
 * `totalMode: "sum"` (default) adds the column up; "none" leaves the footer
 * blank, which is the honest thing to do for a ratio.
 */
export default function ComparisonMatrix({
  title,
  subtitle,
  branches,
  rows,
  rowLabel,
  metric,
  rowTitle,
  rowHint,
  formatValue = defaultFormat,
  totalMode = "sum",
}) {
  const cellVal = (cell) => (cell ? cell[metric] ?? null : null);
  const num = (v) => (typeof v === "number" ? v : 0);
  const colTotal = (bid) => rows.reduce((s, r) => s + num(cellVal(r.cells[bid])), 0);
  const grandTotal = rows.reduce((s, r) => s + num(r.total?.[metric]), 0);
  const summing = totalMode === "sum";

  return (
    <div className="bg-white rounded-lg border overflow-x-auto">
      <div className="px-4 py-3 border-b bg-gray-50/50 flex items-start justify-between gap-3 flex-wrap">
        <div>
          <p className="text-sm font-semibold text-gray-700">{title}</p>
          {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-1.5 text-[11px] text-gray-400 whitespace-nowrap">
          <span>low</span>
          <span className="inline-block w-5 h-3 rounded-sm" style={{ background: "rgba(79,70,229,0.12)" }} />
          <span className="inline-block w-5 h-3 rounded-sm" style={{ background: "rgba(79,70,229,0.32)" }} />
          <span className="inline-block w-5 h-3 rounded-sm" style={{ background: "rgba(79,70,229,0.6)" }} />
          <span>high (per row)</span>
        </div>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="text-left px-4 py-2.5 font-semibold text-gray-600">{rowLabel}</th>
            {branches.map((b) => (
              <th key={b.branch_id} className="text-right px-4 py-2.5 font-semibold text-gray-600 whitespace-nowrap">
                {shortBranchName(b.name)}
              </th>
            ))}
            <th className="text-right px-4 py-2.5 font-semibold text-gray-600">Total</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((r, i) => {
            const rowMax = Math.max(0, ...branches.map((b) => num(cellVal(r.cells[b.branch_id]))));
            return (
              <tr key={i}>
                <td className="px-4 py-2.5 font-medium text-gray-900 whitespace-nowrap"
                    title={rowHint ? rowHint(r) : undefined}>
                  {rowTitle(r)}
                </td>
                {branches.map((b) => {
                  const v = cellVal(r.cells[b.branch_id]);
                  const { style, cls } = heatStyle(num(v), rowMax);
                  return (
                    <td key={b.branch_id} style={style} className={`px-4 py-2.5 text-right tabular-nums ${cls}`}>
                      {formatValue(v)}
                    </td>
                  );
                })}
                <td className="px-4 py-2.5 text-right tabular-nums font-semibold text-gray-900">
                  {formatValue(r.total?.[metric] ?? null)}
                </td>
              </tr>
            );
          })}
          <tr className="bg-gray-50 font-semibold">
            <td className="px-4 py-2.5">Total</td>
            {branches.map((b) => (
              <td key={b.branch_id} className="px-4 py-2.5 text-right tabular-nums">
                {summing ? formatValue(colTotal(b.branch_id)) : ""}
              </td>
            ))}
            <td className="px-4 py-2.5 text-right tabular-nums">
              {summing ? formatValue(grandTotal) : ""}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
