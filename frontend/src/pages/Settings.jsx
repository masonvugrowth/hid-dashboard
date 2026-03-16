/**
 * Settings — branch capacity management
 */
import { useEffect, useState } from "react";
import axios from "axios";

export default function Settings() {
  const [branches, setBranches] = useState([]);
  const [edits, setEdits] = useState({});   // { branchId: { total_rooms, total_room_count, total_dorm_count } }
  const [saving, setSaving] = useState({}); // { branchId: true }
  const [toast, setToast] = useState(null);
  const [loading, setLoading] = useState(true);

  const showToast = (msg, type = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  useEffect(() => {
    axios.get("/api/branches")
      .then(r => {
        const data = r.data.data || [];
        setBranches(data);
        const initEdits = {};
        data.forEach(b => {
          initEdits[b.id] = {
            total_rooms: b.total_rooms ?? "",
            total_room_count: b.total_room_count ?? "",
            total_dorm_count: b.total_dorm_count ?? "",
          };
        });
        setEdits(initEdits);
      })
      .catch(() => setBranches([]))
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (branchId, field, value) => {
    setEdits(prev => ({
      ...prev,
      [branchId]: { ...prev[branchId], [field]: value },
    }));
  };

  const save = async (branch) => {
    const e = edits[branch.id] || {};
    const payload = {};
    const toInt = v => v === "" || v === null ? null : parseInt(v, 10);

    if (toInt(e.total_rooms) !== branch.total_rooms) payload.total_rooms = toInt(e.total_rooms);
    if (toInt(e.total_room_count) !== branch.total_room_count) payload.total_room_count = toInt(e.total_room_count);
    if (toInt(e.total_dorm_count) !== branch.total_dorm_count) payload.total_dorm_count = toInt(e.total_dorm_count);

    if (Object.keys(payload).length === 0) {
      showToast("No changes to save", "info");
      return;
    }

    setSaving(prev => ({ ...prev, [branch.id]: true }));
    try {
      await axios.patch(`/api/branches/${branch.id}/capacity`, payload);
      setBranches(prev => prev.map(b => b.id === branch.id ? { ...b, ...payload } : b));
      showToast(`${branch.name} capacity updated`);
    } catch {
      showToast("Failed to save", "error");
    } finally {
      setSaving(prev => ({ ...prev, [branch.id]: false }));
    }
  };

  return (
    <div className="space-y-5 max-w-3xl">
      <div>
        <h1 className="text-xl font-bold text-gray-800">Settings</h1>
        <p className="text-xs text-gray-400 mt-0.5">Manage branch capacity and room configuration</p>
      </div>

      {toast && (
        <div className={`px-4 py-2.5 rounded-lg text-sm font-medium ${
          toast.type === "error" ? "bg-red-50 text-red-700 border border-red-200"
          : toast.type === "info" ? "bg-gray-50 text-gray-600 border border-gray-200"
          : "bg-green-50 text-green-700 border border-green-200"
        }`}>
          {toast.msg}
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-100">
          <h2 className="font-semibold text-gray-700 text-sm">Branch Capacity</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Total rooms = sellable units for OCC% calculation. Room count / Dorm count = private vs shared split.
          </p>
        </div>

        {loading ? (
          <div className="p-8 text-center text-gray-400 animate-pulse">Loading…</div>
        ) : (
          <div className="divide-y divide-gray-100">
            {branches.map(b => {
              const e = edits[b.id] || {};
              return (
                <div key={b.id} className="px-5 py-4">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="font-medium text-gray-800">{b.name}</p>
                      <p className="text-xs text-gray-400">{b.city} · {b.native_currency}</p>
                    </div>
                    <button
                      onClick={() => save(b)}
                      disabled={saving[b.id]}
                      className="px-3 py-1.5 bg-indigo-600 text-white text-xs font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50"
                    >
                      {saving[b.id] ? "Saving…" : "Save"}
                    </button>
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    <label className="block">
                      <span className="text-xs text-gray-500 font-medium">Total Rooms (OCC base)</span>
                      <input
                        type="number"
                        min="0"
                        value={e.total_rooms}
                        onChange={ev => handleChange(b.id, "total_rooms", ev.target.value)}
                        className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                      />
                    </label>
                    <label className="block">
                      <span className="text-xs text-gray-500 font-medium">Private Rooms</span>
                      <input
                        type="number"
                        min="0"
                        value={e.total_room_count}
                        onChange={ev => handleChange(b.id, "total_room_count", ev.target.value)}
                        className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                      />
                    </label>
                    <label className="block">
                      <span className="text-xs text-gray-500 font-medium">Dorm Beds</span>
                      <input
                        type="number"
                        min="0"
                        value={e.total_dorm_count}
                        onChange={ev => handleChange(b.id, "total_dorm_count", ev.target.value)}
                        className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                      />
                    </label>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
