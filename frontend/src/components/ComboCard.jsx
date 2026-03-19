import VerdictBadge from "./VerdictBadge";

function RoasChip({ value }) {
  if (value == null) return null;
  const color = value >= 3.0 ? "bg-green-100 text-green-700" :
                value >= 1.0 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700";
  return <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${color}`}>{value.toFixed(2)}</span>;
}

export default function ComboCard({ combo, onClick }) {
  const c = combo.copy || {};
  const m = combo.material || {};
  return (
    <div onClick={onClick}
      className="border rounded-lg p-4 bg-white hover:shadow-md cursor-pointer transition-shadow">
      <div className="flex items-center justify-between mb-2">
        <span className="font-mono text-indigo-600 text-xs font-medium">{combo.combo_code}</span>
        <div className="flex items-center gap-2">
          <RoasChip value={combo.roas} />
          <VerdictBadge verdict={combo.verdict} />
        </div>
      </div>

      {/* Copy headline */}
      <p className="text-sm font-medium truncate">{c.headline || "No headline"}</p>
      <p className="text-xs text-gray-400 mt-0.5 truncate">{c.primary_text || ""}</p>

      {/* Material info */}
      <div className="flex items-center gap-2 mt-2 text-xs text-gray-500">
        <span className="px-1.5 py-0.5 bg-gray-100 rounded">{m.material_type || "—"}</span>
        {m.kol_name && <span className="text-purple-600">KOL: {m.kol_name}</span>}
      </div>

      {/* Chips */}
      <div className="flex items-center gap-1.5 mt-2 flex-wrap">
        {combo.target_audience && (
          <span className="text-[10px] px-1.5 py-0.5 bg-indigo-50 text-indigo-600 rounded">{combo.target_audience}</span>
        )}
        {combo.language && (
          <span className="text-[10px] px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded">{combo.language}</span>
        )}
        {combo.channel && (
          <span className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">{combo.channel}</span>
        )}
        {combo.spend_vnd != null && (
          <span className="text-[10px] text-gray-400">
            {new Intl.NumberFormat("vi-VN", {notation: "compact"}).format(combo.spend_vnd)} VND
          </span>
        )}
      </div>
    </div>
  );
}
