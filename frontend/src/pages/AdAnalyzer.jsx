/**
 * AdAnalyzer — AI-powered ad analysis dashboard.
 * Funnel chart, Angle performance, TA×Angle heatmap, Recommendations.
 */
import { useEffect, useState } from "react";
import { useBranch } from "../context/BranchContext";
import { listResults, getInsights, analyzeBatch } from "../api/analyzer";
import { getTAClasses, AUDIENCES } from "../constants/audiences";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts";

const REC_COLORS = {
  scale_up: "bg-green-100 text-green-700",
  optimize: "bg-amber-100 text-amber-700",
  pause: "bg-red-100 text-red-700",
  test_new: "bg-blue-100 text-blue-700",
  insufficient_data: "bg-gray-100 text-gray-500",
};
const REC_LABELS = {
  scale_up: "Scale Up",
  optimize: "Optimize",
  pause: "Pause",
  test_new: "Test New",
  insufficient_data: "Need Data",
};

const ANGLE_COLORS = ["#6366f1", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4"];

const fmt = (v) => v != null ? new Intl.NumberFormat("vi-VN", { notation: "compact" }).format(v) : "—";

export default function AdAnalyzer() {
  const { selected, isAll } = useBranch();
  const [insights, setInsights] = useState(null);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

  const load = () => {
    setLoading(true);
    const params = !isAll && selected ? { branch_id: selected } : {};
    Promise.all([getInsights(params), listResults(params)])
      .then(([ins, res]) => { setInsights(ins); setResults(res); })
      .finally(() => setLoading(false));
  };
  useEffect(load, [selected]);

  const handleBatchAnalyze = () => {
    if (!selected || isAll) return;
    setAnalyzing(true);
    analyzeBatch(selected, true)
      .then(() => setTimeout(load, 3000)) // Reload after a short delay
      .finally(() => setAnalyzing(false));
  };

  if (loading) return <div className="text-gray-400 text-sm animate-pulse">Loading analyzer...</div>;

  const funnel = insights?.funnel_aggregate || {};
  const anglePerfData = insights?.angle_performance || [];
  const taAngleData = insights?.ta_angle_matrix || [];
  const recSummary = insights?.recommendation_summary || {};

  // Build funnel stages
  const funnelStages = [
    { label: "Impressions", value: funnel.impressions, rate: null },
    { label: "Clicks", value: funnel.clicks, rate: funnel.ctr, rateLabel: "CTR" },
    { label: "LP Views", value: funnel.lp_views, rate: funnel.lp_view_rate, rateLabel: "LP View %" },
    { label: "Add to Cart", value: funnel.add_to_cart, rate: funnel.atc_rate, rateLabel: "ATC %" },
    { label: "Checkout", value: funnel.checkout, rate: funnel.checkout_rate, rateLabel: "CO %" },
    { label: "Purchase", value: funnel.purchases, rate: funnel.purchase_rate, rateLabel: "Purch %" },
  ];

  // Build TA×Angle matrix data
  const allAngles = [...new Set(taAngleData.map(d => d.angle))];
  const allTAs = [...new Set(taAngleData.map(d => d.ta))];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Ad Analyzer</h1>
          <p className="text-sm text-gray-400">{insights?.total_analyzed || 0} ads analyzed</p>
        </div>
        <button onClick={handleBatchAnalyze}
          disabled={analyzing || isAll || !selected}
          className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50">
          {analyzing ? "Analyzing..." : "⬡ Analyze All Ads"}
        </button>
      </div>

      {/* Funnel Visualization */}
      <div className="bg-white rounded-xl border p-5 mb-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Conversion Funnel</h2>
        <div className="flex items-end gap-1">
          {funnelStages.map((stage, i) => {
            const maxVal = funnelStages[0].value || 1;
            const pct = stage.value ? Math.max((stage.value / maxVal) * 100, 8) : 8;
            const isLow = stage.rate != null && (
              (stage.rateLabel === "CTR" && stage.rate < 1) ||
              (stage.rateLabel === "ATC %" && stage.rate < 5) ||
              (stage.rateLabel === "CO %" && stage.rate < 50) ||
              (stage.rateLabel === "Purch %" && stage.rate < 60)
            );
            return (
              <div key={i} className="flex-1 flex flex-col items-center gap-1">
                <span className="text-xs font-medium text-gray-700">{fmt(stage.value)}</span>
                <div
                  className={`w-full rounded-t-md transition-all ${isLow ? "bg-red-400" : "bg-indigo-500"}`}
                  style={{ height: `${pct}px`, minHeight: "8px", maxHeight: "120px" }}
                />
                <span className="text-[10px] text-gray-500 text-center">{stage.label}</span>
                {stage.rate != null && (
                  <span className={`text-[10px] font-medium ${isLow ? "text-red-600" : "text-green-600"}`}>
                    {stage.rate}%
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Angle Performance Chart */}
        <div className="bg-white rounded-xl border p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Angle Performance (Avg CTR %)</h2>
          {anglePerfData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={anglePerfData} layout="vertical" margin={{ left: 80 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="angle" tick={{ fontSize: 11 }} width={75} />
                <Tooltip formatter={(v) => `${v}%`} />
                <Bar dataKey="avg_ctr" radius={[0, 4, 4, 0]}>
                  {anglePerfData.map((_, i) => (
                    <Cell key={i} fill={ANGLE_COLORS[i % ANGLE_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="text-gray-400 text-sm">No angle data yet. Analyze ads first.</p>}
        </div>

        {/* Recommendation Summary */}
        <div className="bg-white rounded-xl border p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Recommendation Summary</h2>
          <div className="space-y-2">
            {Object.entries(recSummary).map(([type, count]) => (
              <div key={type} className="flex items-center justify-between">
                <span className={`text-xs px-2 py-1 rounded font-medium ${REC_COLORS[type] || "bg-gray-100 text-gray-600"}`}>
                  {REC_LABELS[type] || type}
                </span>
                <span className="text-sm font-semibold text-gray-700">{count}</span>
              </div>
            ))}
            {Object.keys(recSummary).length === 0 && <p className="text-gray-400 text-sm">No recommendations yet.</p>}
          </div>
        </div>
      </div>

      {/* TA × Angle Matrix */}
      {taAngleData.length > 0 && (
        <div className="bg-white rounded-xl border p-5 mb-6 overflow-x-auto">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">TA × Angle Matrix (Avg ROAS)</h2>
          <table className="text-xs w-full">
            <thead>
              <tr>
                <th className="text-left py-1 px-2 text-gray-500">TA \ Angle</th>
                {allAngles.map(a => <th key={a} className="py-1 px-2 text-gray-500 text-center">{a}</th>)}
              </tr>
            </thead>
            <tbody>
              {allTAs.map(ta => (
                <tr key={ta}>
                  <td className="py-1 px-2 font-medium">{ta}</td>
                  {allAngles.map(angle => {
                    const cell = taAngleData.find(d => d.ta === ta && d.angle === angle);
                    if (!cell) return <td key={angle} className="py-1 px-2 text-center text-gray-300">—</td>;
                    const roas = cell.avg_roas;
                    const bg = roas >= 3 ? "bg-green-100 text-green-700" :
                               roas >= 1 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700";
                    return (
                      <td key={angle} className="py-1 px-2 text-center">
                        <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${bg}`}>
                          {roas.toFixed(1)}x <span className="text-[9px] opacity-60">({cell.count})</span>
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Analysis Results Cards */}
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Analysis Results ({results.length})</h2>
      </div>
      {results.length === 0 ? (
        <div className="text-gray-400 text-sm">No analysis results. Click "Analyze All Ads" to start.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {results.map(r => (
            <div key={r.id} className="bg-white rounded-xl border p-4 hover:shadow-md transition-shadow">
              {/* Header */}
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-indigo-600 text-xs font-medium">{r.combo_code}</span>
                <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${REC_COLORS[r.recommendation_type] || "bg-gray-100"}`}>
                  {REC_LABELS[r.recommendation_type] || r.recommendation_type}
                </span>
              </div>

              {/* Copy headline */}
              <p className="text-sm font-medium truncate">{r.combo?.copy_headline || "—"}</p>
              <span className="text-[10px] text-gray-400">{r.combo?.material_type}</span>

              {/* Detected Angles */}
              {r.detected_angles?.length > 0 && (
                <div className="flex gap-1 mt-2 flex-wrap">
                  {r.detected_angles.map(a => (
                    <span key={a} className="text-[10px] px-1.5 py-0.5 bg-violet-50 text-violet-600 rounded">{a}</span>
                  ))}
                </div>
              )}

              {/* Detected TA */}
              {r.detected_ta?.length > 0 && (
                <div className="flex gap-1 mt-1 flex-wrap">
                  {r.detected_ta.map(ta => {
                    const tc = getTAClasses(ta);
                    return <span key={ta} className={`text-[10px] px-1.5 py-0.5 rounded ${tc.bg} ${tc.text}`}>{ta}</span>;
                  })}
                </div>
              )}

              {/* Keypoints */}
              {r.keypoints?.length > 0 && (
                <div className="mt-2 space-y-0.5">
                  {r.keypoints.slice(0, 3).map((kp, i) => (
                    <p key={i} className="text-[10px] text-gray-500 flex items-start gap-1">
                      <span className="text-indigo-400 mt-px">•</span> {kp}
                    </p>
                  ))}
                </div>
              )}

              {/* Mini metrics */}
              <div className="grid grid-cols-3 gap-1 mt-3 text-center">
                <div className="bg-gray-50 rounded px-1 py-1">
                  <p className="text-[9px] text-gray-400">ROAS</p>
                  <p className={`text-[11px] font-semibold ${
                    r.combo?.roas >= 3 ? "text-green-600" : r.combo?.roas >= 1 ? "text-amber-500" : "text-red-500"
                  }`}>{r.combo?.roas?.toFixed(2) || "—"}</p>
                </div>
                <div className="bg-gray-50 rounded px-1 py-1">
                  <p className="text-[9px] text-gray-400">Spend</p>
                  <p className="text-[11px] font-medium">{fmt(r.combo?.spend_vnd)}</p>
                </div>
                <div className="bg-gray-50 rounded px-1 py-1">
                  <p className="text-[9px] text-gray-400">Purchases</p>
                  <p className="text-[11px] font-medium">{r.combo?.purchases ?? "—"}</p>
                </div>
              </div>

              {/* Recommendation */}
              <p className="text-[10px] text-gray-500 mt-2 italic">{r.ai_recommendation}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
