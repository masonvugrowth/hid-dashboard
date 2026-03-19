/**
 * AdCombos — PRIMARY Phase 4 page. Copy × Material = verdict.
 * Filter bar, combo cards, detail drawer, add combo modal.
 */
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useBranch } from "../context/BranchContext";
import { useAuth } from "../context/AuthContext";
import { listCombos, getCombo, createCombo, updateCombo, triggerSync, comboInsights, importFromMeta } from "../api/combos";
import { listCopies } from "../api/copies";
import { listMaterials } from "../api/materials";
import ComboCard from "../components/ComboCard";
import VerdictBadge from "../components/VerdictBadge";

const AUDIENCES = ["Solo", "Couple", "Friend Group", "Family", "Business", "High Intent", "Generic"];
const CHANNELS = ["Facebook", "Instagram", "TikTok", "YouTube", "Meta", "Google"];
const LANGUAGES = ["Vietnamese", "English", "Japanese", "Korean", "Thai", "Indonesian", "Malay"];
const VERDICTS = ["winning", "good", "neutral", "underperformer", "kill"];
const RUN_STATUSES = ["Active", "Paused", "Ended"];

export default function AdCombos() {
  const { selected, isAll } = useBranch();
  const { isAdmin } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const [combos, setCombos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [insights, setInsights] = useState(null);
  const [detail, setDetail] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);

  // Filters from URL params
  const f = {
    target_audience: searchParams.get("target_audience") || "",
    channel: searchParams.get("channel") || "",
    language: searchParams.get("language") || "",
    verdict: searchParams.get("verdict") || "",
    run_status: searchParams.get("run_status") || "",
  };

  const setFilter = (key, val) => {
    const p = new URLSearchParams(searchParams);
    if (val) p.set(key, val); else p.delete(key);
    setSearchParams(p);
  };

  const load = () => {
    setLoading(true);
    const p = { ...f };
    if (!isAll && selected) p.branch_id = selected;
    Object.keys(p).forEach(k => { if (!p[k]) delete p[k]; });
    Promise.all([
      listCombos(p),
      comboInsights({ branch_id: !isAll ? selected : undefined }),
    ]).then(([c, ins]) => {
      setCombos(c);
      setInsights(ins);
    }).finally(() => setLoading(false));
  };
  useEffect(load, [selected, searchParams.toString()]);

  const openDetail = (id) => {
    getCombo(id).then(setDetail);
  };

  const saveVerdict = (id, verdict, notes) => {
    updateCombo(id, { verdict, verdict_notes: notes }).then(d => { setDetail(d); load(); });
  };

  return (
    <div>
      {/* Header + Insights Strip */}
      <div className="flex items-center justify-between mb-3">
        <h1 className="text-xl font-bold text-gray-900">Ad Combos</h1>
        <div className="flex gap-2">
          {isAdmin && (
            <>
              <button onClick={() => triggerSync().then(load)}
                className="px-3 py-1.5 text-xs border rounded text-gray-600 hover:bg-gray-50">Sync ROAS</button>
              <button
                onClick={() => {
                  setImporting(true);
                  setImportResult(null);
                  importFromMeta({
                    branch_id: !isAll ? selected : undefined,
                    status_filter: "ACTIVE",
                  }).then(r => {
                    setImportResult(r);
                    load();
                  }).catch(err => {
                    setImportResult({ error: err.response?.data?.detail || "Import failed" });
                  }).finally(() => setImporting(false));
                }}
                disabled={importing}
                className="px-3 py-1.5 text-xs border border-blue-300 rounded text-blue-600 hover:bg-blue-50 disabled:opacity-50"
              >
                {importing ? "Importing..." : "Import from Meta"}
              </button>
            </>
          )}
          <button onClick={() => setShowAdd(true)}
            className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700">+ Add Combo</button>
        </div>
      </div>

      {/* Import result banner */}
      {importResult && (
        <div className={`mb-3 p-3 rounded text-sm flex items-center justify-between ${
          importResult.error ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"
        }`}>
          {importResult.error ? (
            <span>{importResult.error}</span>
          ) : (
            <span>
              Meta Import: {importResult.stats?.ads_fetched || 0} ads fetched
              {" → "}{importResult.stats?.copies_created || 0} copies,
              {" "}{importResult.stats?.materials_created || 0} materials,
              {" "}{importResult.stats?.combos_created || 0} combos created
              {importResult.stats?.skipped ? ` (${importResult.stats.skipped} skipped)` : ""}
            </span>
          )}
          <button onClick={() => setImportResult(null)} className="ml-2 text-gray-400 hover:text-gray-600">&times;</button>
        </div>
      )}

      {insights && (
        <div className="flex gap-3 mb-4 text-xs">
          <span className="px-2 py-1 bg-gray-100 rounded">Total: {insights.total_combos}</span>
          <span className="px-2 py-1 bg-green-100 text-green-700 rounded">Winning: {insights.winning_count}</span>
          {insights.top_by_roas?.[0] && (
            <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded">
              Top ROAS: {insights.top_by_roas[0].roas.toFixed(2)} ({insights.top_by_roas[0].combo_code})
            </span>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {[
          ["target_audience", "Audience", AUDIENCES],
          ["channel", "Channel", CHANNELS],
          ["language", "Language", LANGUAGES],
          ["verdict", "Verdict", VERDICTS],
          ["run_status", "Status", RUN_STATUSES],
        ].map(([key, label, opts]) => (
          <select key={key} value={f[key]} onChange={e => setFilter(key, e.target.value)}
            className="border rounded px-2 py-1 text-sm">
            <option value="">All {label}</option>
            {opts.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        ))}
      </div>

      {/* Combo Cards */}
      {loading ? (
        <div className="text-gray-400 text-sm animate-pulse">Loading...</div>
      ) : combos.length === 0 ? (
        <div className="text-gray-400 text-sm">No combos found. Create one to get started.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {combos.map(cb => (
            <ComboCard key={cb.id} combo={cb} onClick={() => openDetail(cb.id)} />
          ))}
        </div>
      )}

      {/* Detail Drawer */}
      {detail && (
        <div className="fixed inset-0 z-50 flex items-center justify-end">
          <div className="absolute inset-0 bg-black/30" onClick={() => setDetail(null)} />
          <div className="relative w-[480px] h-full bg-white shadow-xl overflow-y-auto">
            <div className="sticky top-0 bg-white border-b px-4 py-3 flex items-center justify-between">
              <h3 className="font-semibold text-sm">
                <span className="font-mono text-indigo-600">{detail.combo_code}</span>
              </h3>
              <button onClick={() => setDetail(null)} className="text-gray-400 hover:text-gray-600 text-lg">&times;</button>
            </div>
            <div className="p-4 space-y-4">
              {/* Verdict */}
              <div className="flex items-center gap-3">
                <VerdictBadge verdict={detail.verdict} />
                {detail.verdict_source && <span className="text-xs text-gray-400">({detail.verdict_source})</span>}
                {detail.roas != null && (
                  <span className={`text-sm font-medium ${
                    detail.roas >= 3 ? "text-green-600" : detail.roas >= 1 ? "text-amber-500" : "text-red-500"
                  }`}>ROAS {detail.roas.toFixed(2)}</span>
                )}
              </div>

              {/* Copy */}
              <div className="bg-gray-50 rounded p-3">
                <label className="text-xs font-medium text-gray-500">Copy — {detail.copy?.copy_code}</label>
                <p className="text-sm font-medium mt-1">{detail.copy?.headline || "—"}</p>
                <p className="text-sm mt-1 whitespace-pre-wrap text-gray-700">{detail.copy?.primary_text || "—"}</p>
                {detail.copy?.landing_page_url && (
                  <a href={detail.copy.landing_page_url} target="_blank" rel="noreferrer"
                    className="text-xs text-blue-500 hover:underline mt-1 block">Landing page</a>
                )}
              </div>

              {/* Material */}
              <div className="bg-gray-50 rounded p-3">
                <label className="text-xs font-medium text-gray-500">Material — {detail.material?.material_code}</label>
                <div className="grid grid-cols-2 gap-2 mt-1 text-xs">
                  <div><span className="text-gray-400">Type:</span> {detail.material?.material_type}</div>
                  <div><span className="text-gray-400">Design:</span> {detail.material?.design_type || "—"}</div>
                  {detail.material?.kol_name && <div className="col-span-2 text-purple-600">KOL: {detail.material.kol_name}</div>}
                </div>
                {detail.material?.file_link && (
                  <a href={detail.material.file_link} target="_blank" rel="noreferrer"
                    className="text-xs text-blue-500 hover:underline mt-1 block">Open file</a>
                )}
              </div>

              {/* Primary Metrics: Cost · Purchase · Revenue · ROAS */}
              <div className="grid grid-cols-4 gap-2 text-xs">
                <div className="bg-blue-50 rounded p-2 text-center">
                  <span className="text-blue-400 text-[10px]">Cost</span>
                  <p className="font-semibold text-blue-700">{detail.spend_vnd != null ? new Intl.NumberFormat("vi-VN", {notation: "compact"}).format(detail.spend_vnd) : "—"}</p>
                </div>
                <div className="bg-purple-50 rounded p-2 text-center">
                  <span className="text-purple-400 text-[10px]">Purchase</span>
                  <p className="font-semibold text-purple-700">{detail.purchases ?? "—"}</p>
                </div>
                <div className="bg-green-50 rounded p-2 text-center">
                  <span className="text-green-400 text-[10px]">Revenue</span>
                  <p className="font-semibold text-green-700">{detail.revenue_vnd != null ? new Intl.NumberFormat("vi-VN", {notation: "compact"}).format(detail.revenue_vnd) : "—"}</p>
                </div>
                <div className={`rounded p-2 text-center ${
                  detail.roas >= 3 ? "bg-green-50" : detail.roas >= 1 ? "bg-amber-50" : detail.roas != null ? "bg-red-50" : "bg-gray-50"
                }`}>
                  <span className="text-gray-400 text-[10px]">ROAS</span>
                  <p className={`font-bold ${
                    detail.roas >= 3 ? "text-green-700" : detail.roas >= 1 ? "text-amber-600" : detail.roas != null ? "text-red-600" : "text-gray-400"
                  }`}>{detail.roas != null ? detail.roas.toFixed(2) : "—"}</p>
                </div>
              </div>

              {/* Secondary Metrics */}
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="bg-gray-50 rounded p-2 text-center">
                  <span className="text-gray-400 text-[10px]">Impressions</span>
                  <p className="font-medium">{detail.impressions?.toLocaleString() || "—"}</p>
                </div>
                <div className="bg-gray-50 rounded p-2 text-center">
                  <span className="text-gray-400 text-[10px]">Clicks</span>
                  <p className="font-medium">{detail.clicks?.toLocaleString() || "—"}</p>
                </div>
                <div className="bg-gray-50 rounded p-2 text-center">
                  <span className="text-gray-400 text-[10px]">Leads</span>
                  <p className="font-medium">{detail.leads ?? "—"}</p>
                </div>
              </div>

              {/* Verdict editor */}
              <div className="border-t pt-3">
                <label className="text-xs font-medium text-gray-500">Set Verdict</label>
                <div className="flex gap-1 mt-1 flex-wrap">
                  {VERDICTS.map(v => (
                    <button key={v} onClick={() => {
                      const notes = v !== detail.verdict ? prompt("Verdict notes (optional):") : null;
                      saveVerdict(detail.id, v, notes);
                    }}
                      className={`text-xs px-2 py-1 rounded border ${
                        detail.verdict === v ? "bg-indigo-600 text-white border-indigo-600" : "text-gray-600 hover:bg-gray-100"
                      }`}>{v}</button>
                  ))}
                </div>
                {detail.verdict_notes && (
                  <p className="text-xs text-gray-500 mt-1">Notes: {detail.verdict_notes}</p>
                )}
              </div>

              {/* Meta ad name + run status */}
              <div className="border-t pt-3 space-y-2">
                <div>
                  <label className="text-xs text-gray-500">Meta Ad Name</label>
                  <input defaultValue={detail.meta_ad_name || ""} onBlur={e => {
                    if (e.target.value !== (detail.meta_ad_name || ""))
                      updateCombo(detail.id, { meta_ad_name: e.target.value }).then(d => setDetail(d));
                  }} className="w-full border rounded px-2 py-1 text-xs font-mono mt-1" placeholder="Paste from Meta Ads Manager" />
                </div>
                <div>
                  <label className="text-xs text-gray-500">Run Status</label>
                  <select defaultValue={detail.run_status || ""} onChange={e => {
                    updateCombo(detail.id, { run_status: e.target.value || null }).then(d => { setDetail(d); load(); });
                  }} className="w-full border rounded px-2 py-1 text-xs mt-1">
                    <option value="">Not set</option>
                    {RUN_STATUSES.map(s => <option key={s}>{s}</option>)}
                  </select>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add Combo Modal */}
      {showAdd && <AddComboModal branchId={!isAll ? selected : null} onClose={() => setShowAdd(false)} onCreated={() => { setShowAdd(false); load(); }} />}
    </div>
  );
}

function AddComboModal({ branchId, onClose, onCreated }) {
  const [copies, setCopies] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [copyId, setCopyId] = useState("");
  const [materialId, setMaterialId] = useState("");
  const [metaAdName, setMetaAdName] = useState("");
  const [runStatus, setRunStatus] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const p = branchId ? { branch_id: branchId } : {};
    Promise.all([listCopies(p), listMaterials(p)]).then(([c, m]) => { setCopies(c); setMaterials(m); });
  }, [branchId]);

  const save = () => {
    setSaving(true);
    setError("");
    createCombo({
      copy_id: copyId,
      material_id: materialId,
      meta_ad_name: metaAdName || undefined,
      run_status: runStatus || undefined,
    }).then(onCreated).catch(err => {
      setError(err.response?.data?.detail || "Failed to create combo");
      setSaving(false);
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Add Combo</h2>
        {error && <div className="mb-3 p-2 bg-red-50 text-red-700 text-sm rounded">{error}</div>}
        <div className="space-y-3">
          <div>
            <label className="text-xs text-gray-500">Copy *</label>
            <select value={copyId} onChange={e => setCopyId(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm mt-1">
              <option value="">Select copy...</option>
              {copies.map(c => (
                <option key={c.id} value={c.id}>{c.copy_code} — {c.headline?.substring(0, 50) || c.primary_text?.substring(0, 50) || "No text"}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500">Material *</label>
            <select value={materialId} onChange={e => setMaterialId(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm mt-1">
              <option value="">Select material...</option>
              {materials.map(m => (
                <option key={m.id} value={m.id}>{m.material_code} — {m.material_type} {m.kol_name ? `(KOL: ${m.kol_name})` : ""}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500">Meta Ad Name (optional)</label>
            <input value={metaAdName} onChange={e => setMetaAdName(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm mt-1 font-mono" placeholder="Paste from Meta" />
          </div>
          <div>
            <label className="text-xs text-gray-500">Run Status</label>
            <select value={runStatus} onChange={e => setRunStatus(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm mt-1">
              <option value="">Not set</option>
              <option>Active</option><option>Paused</option><option>Ended</option>
            </select>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="px-3 py-1.5 text-sm text-gray-600">Cancel</button>
          <button onClick={save} disabled={!copyId || !materialId || saving}
            className="px-4 py-1.5 bg-indigo-600 text-white text-sm rounded disabled:opacity-50">
            {saving ? "Creating..." : "Create Combo"}
          </button>
        </div>
      </div>
    </div>
  );
}
