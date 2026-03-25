/**
 * Email Marketing Dashboard — GHL email performance analytics.
 * Daily sync from GoHighLevel API tracks cumulative stats per workflow.
 */
import { useEffect, useState } from "react";
import {
  getEmailSummary,
  getEmailDaily,
  getEmailByWorkflow,
} from "../api/emailMarketing";
import TrendChart from "../components/TrendChart";

function pct(val) {
  if (val == null) return "—";
  return `${(val * 100).toFixed(1)}%`;
}

function rateBand(rate, thresholds = [0.3, 0.2, 0.1]) {
  if (rate >= thresholds[0]) return "text-green-700 bg-green-50";
  if (rate >= thresholds[1]) return "text-yellow-700 bg-yellow-50";
  if (rate >= thresholds[2]) return "text-orange-700 bg-orange-50";
  return "text-red-700 bg-red-50";
}

function badRate(rate, thresholds = [0.02, 0.05, 0.10]) {
  if (rate <= thresholds[0]) return "text-green-700 bg-green-50";
  if (rate <= thresholds[1]) return "text-yellow-700 bg-yellow-50";
  if (rate <= thresholds[2]) return "text-orange-700 bg-orange-50";
  return "text-red-700 bg-red-50";
}

const TABS = ["overview", "workflows"];
const TAB_LABELS = { overview: "Overview", workflows: "Workflows" };

export default function EmailMarketing() {
  const today = new Date().toISOString().slice(0, 10);
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 29);
    return d.toISOString().slice(0, 10);
  });
  const [dateTo, setDateTo] = useState(today);
  const [tab, setTab] = useState("overview");

  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [daily, setDaily] = useState([]);
  const [workflows, setWorkflows] = useState([]);

  const params = { date_from: dateFrom, date_to: dateTo };

  useEffect(() => {
    setLoading(true);

    if (tab === "overview") {
      Promise.all([
        getEmailSummary(params),
        getEmailDaily(params),
        getEmailByWorkflow(params),
      ])
        .then(([s, d, w]) => {
          setSummary(s);
          setDaily(d || []);
          setWorkflows(w || []);
        })
        .catch(console.error)
        .finally(() => setLoading(false));
    } else if (tab === "workflows") {
      getEmailByWorkflow(params)
        .then(w => setWorkflows(w || []))
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [tab, dateFrom, dateTo]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-800">Email Marketing</h1>
          <p className="text-sm text-gray-500">GHL workflow email performance (Saigon)</p>
        </div>
        <div className="flex gap-2 items-center text-sm">
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-1.5" />
          <span className="text-gray-400">&rarr;</span>
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-1.5" />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              tab === t ? "bg-white text-gray-800 shadow-sm" : "text-gray-500 hover:text-gray-700"
            }`}>
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-gray-400 animate-pulse">Loading...</div>
      ) : tab === "overview" ? (
        <OverviewTab summary={summary} daily={daily} workflows={workflows} />
      ) : (
        <WorkflowsTab workflows={workflows} />
      )}
    </div>
  );
}

/* ── Overview Tab ────────────────────────────────────────────────────────── */
function OverviewTab({ summary, daily, workflows }) {
  if (!summary || summary.total_sent === 0) {
    return <div className="bg-white rounded-xl border p-8 text-center text-gray-400">No email data for this range.</div>;
  }

  const kpis = [
    { label: "Total Sent", value: summary.total_sent.toLocaleString(), color: "text-indigo-700 bg-indigo-50" },
    { label: "Delivered", value: summary.total_delivered.toLocaleString(), color: "text-blue-700 bg-blue-50" },
    { label: "Open Rate", value: pct(summary.open_rate), color: rateBand(summary.open_rate, [0.25, 0.15, 0.08]) },
    { label: "Click Rate", value: pct(summary.click_rate), color: rateBand(summary.click_rate, [0.05, 0.02, 0.01]) },
    { label: "Bounce Rate", value: pct(summary.bounce_rate), color: badRate(summary.bounce_rate) },
    { label: "Unsub Rate", value: pct(summary.unsubscribe_rate), color: badRate(summary.unsubscribe_rate) },
  ];

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {kpis.map(k => (
          <div key={k.label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <p className="text-xs text-gray-500 mb-1">{k.label}</p>
            <p className={`text-lg font-bold ${k.color} px-2 py-0.5 rounded inline-block`}>{k.value}</p>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TrendChart
          title="Daily Opens & Clicks"
          data={daily}
          xKey="date"
          lines={[
            { key: "opened", name: "Opens", color: "#10b981" },
            { key: "clicked", name: "Clicks", color: "#8b5cf6" },
          ]}
          formatY={v => v}
        />
        <TrendChart
          title="Daily Sent & Bounced"
          data={daily}
          xKey="date"
          bars={[{ key: "sent", name: "Sent", color: "#6366f1" }]}
          lines={[{ key: "bounced", name: "Bounced", color: "#ef4444" }]}
          formatY={v => v}
        />
      </div>

      {/* Top Workflows */}
      {workflows.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
          <p className="px-4 pt-4 text-sm font-semibold text-gray-700">Top Workflows</p>
          <table className="w-full text-sm mt-2">
            <thead>
              <tr className="text-xs text-gray-500 uppercase tracking-wide border-b border-gray-100">
                <th className="px-4 py-2 text-left">Workflow</th>
                <th className="px-4 py-2 text-right">Sent</th>
                <th className="px-4 py-2 text-right">Opens</th>
                <th className="px-4 py-2 text-right">Open%</th>
                <th className="px-4 py-2 text-right">Clicks</th>
                <th className="px-4 py-2 text-right">Click%</th>
                <th className="px-4 py-2 text-right">Bounce%</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {workflows.slice(0, 10).map(w => (
                <tr key={w.workflow_id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 text-gray-700 font-medium text-xs truncate max-w-[250px]">
                    {w.workflow_name}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">{w.sent.toLocaleString()}</td>
                  <td className="px-4 py-2 text-right tabular-nums text-green-700">{w.unique_opened.toLocaleString()}</td>
                  <td className="px-4 py-2 text-right">
                    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${rateBand(w.open_rate, [0.25, 0.15, 0.08])}`}>
                      {pct(w.open_rate)}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-purple-700">{w.unique_clicked.toLocaleString()}</td>
                  <td className="px-4 py-2 text-right">
                    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${rateBand(w.click_rate, [0.05, 0.02, 0.01])}`}>
                      {pct(w.click_rate)}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right">
                    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${badRate(w.bounce_rate)}`}>
                      {pct(w.bounce_rate)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ── Workflows Tab ───────────────────────────────────────────────────────── */
function WorkflowsTab({ workflows }) {
  if (workflows.length === 0) {
    return <div className="bg-white rounded-xl border p-8 text-center text-gray-400">No workflow data.</div>;
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-gray-500 uppercase tracking-wide border-b border-gray-100">
            <th className="px-4 py-3 text-left">Workflow</th>
            <th className="px-4 py-3 text-right">Sent</th>
            <th className="px-4 py-3 text-right">Delivered</th>
            <th className="px-4 py-3 text-right">Opens</th>
            <th className="px-4 py-3 text-right">Open%</th>
            <th className="px-4 py-3 text-right">Clicks</th>
            <th className="px-4 py-3 text-right">Click%</th>
            <th className="px-4 py-3 text-right">Bounces</th>
            <th className="px-4 py-3 text-right">Bounce%</th>
            <th className="px-4 py-3 text-right">Unsubs</th>
            <th className="px-4 py-3 text-right">Unsub%</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {workflows.map(w => (
            <tr key={w.workflow_id} className="hover:bg-gray-50">
              <td className="px-4 py-2.5 text-gray-700 font-medium text-xs truncate max-w-[250px]">
                {w.workflow_name}
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums">{w.sent.toLocaleString()}</td>
              <td className="px-4 py-2.5 text-right tabular-nums">{w.delivered.toLocaleString()}</td>
              <td className="px-4 py-2.5 text-right tabular-nums text-green-700">{w.unique_opened.toLocaleString()}</td>
              <td className="px-4 py-2.5 text-right">
                <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${rateBand(w.open_rate, [0.25, 0.15, 0.08])}`}>
                  {pct(w.open_rate)}
                </span>
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums text-purple-700">{w.unique_clicked.toLocaleString()}</td>
              <td className="px-4 py-2.5 text-right">
                <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${rateBand(w.click_rate, [0.05, 0.02, 0.01])}`}>
                  {pct(w.click_rate)}
                </span>
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums text-red-600">{w.bounced.toLocaleString()}</td>
              <td className="px-4 py-2.5 text-right">
                <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${badRate(w.bounce_rate)}`}>
                  {pct(w.bounce_rate)}
                </span>
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums text-orange-600">{w.unsubscribed.toLocaleString()}</td>
              <td className="px-4 py-2.5 text-right">
                <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${badRate(w.unsubscribe_rate)}`}>
                  {pct(w.unsubscribe_rate)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
