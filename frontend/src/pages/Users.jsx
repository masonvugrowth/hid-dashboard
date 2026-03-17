/**
 * User Management — admin only
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";

const ROLE_LABELS = { admin: "Admin", editor: "Editor", viewer: "Viewer" };
const ROLE_COLORS = {
  admin:  "bg-indigo-100 text-indigo-700",
  editor: "bg-emerald-100 text-emerald-700",
  viewer: "bg-gray-100 text-gray-600",
};

export default function Users() {
  const { isAdmin, user: me } = useAuth();
  const navigate = useNavigate();
  const [users,   setUsers]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal,   setModal]   = useState(null);  // null | "create" | user object (edit)

  useEffect(() => {
    if (!isAdmin) { navigate("/home"); return; }
    fetchUsers();
  }, []);

  function fetchUsers() {
    setLoading(true);
    axios.get("/api/auth/users")
      .then(r => setUsers(r.data.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  async function handleDeactivate(u) {
    if (!confirm(`Deactivate ${u.email}?`)) return;
    await axios.delete(`/api/auth/users/${u.id}`);
    fetchUsers();
  }

  async function handleReactivate(u) {
    await axios.put(`/api/auth/users/${u.id}`, { is_active: true });
    fetchUsers();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-800">User Management</h1>
          <p className="text-sm text-gray-500">Manage team access — admin only</p>
        </div>
        <button onClick={() => setModal("create")}
          className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-500 transition-colors">
          + Add User
        </button>
      </div>

      {loading ? (
        <div className="text-gray-400 animate-pulse py-8 text-center">Loading…</div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-xs text-gray-500 uppercase border-b border-gray-100">
                <th className="px-5 py-3 text-left">Name / Email</th>
                <th className="px-5 py-3 text-left">Role</th>
                <th className="px-5 py-3 text-left">Status</th>
                <th className="px-5 py-3 text-left">Created</th>
                <th className="px-5 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {users.map(u => (
                <tr key={u.id} className={`hover:bg-gray-50 ${!u.is_active ? "opacity-50" : ""}`}>
                  <td className="px-5 py-3">
                    <div className="font-medium text-gray-800">{u.name || "—"}</div>
                    <div className="text-xs text-gray-400">{u.email}</div>
                  </td>
                  <td className="px-5 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${ROLE_COLORS[u.role] || ROLE_COLORS.viewer}`}>
                      {ROLE_LABELS[u.role] || u.role}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    <span className={`text-xs font-medium ${u.is_active ? "text-emerald-600" : "text-gray-400"}`}>
                      {u.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-gray-400 text-xs">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-5 py-3 text-right space-x-2">
                    <button onClick={() => setModal(u)}
                      className="text-xs text-indigo-600 hover:underline">Edit</button>
                    {u.id !== me?.id && (
                      u.is_active
                        ? <button onClick={() => handleDeactivate(u)}
                            className="text-xs text-red-500 hover:underline">Deactivate</button>
                        : <button onClick={() => handleReactivate(u)}
                            className="text-xs text-emerald-600 hover:underline">Reactivate</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {modal && (
        <UserModal
          user={modal === "create" ? null : modal}
          onClose={() => setModal(null)}
          onSaved={() => { setModal(null); fetchUsers(); }}
        />
      )}
    </div>
  );
}

// ── Create / Edit modal ───────────────────────────────────────────────────────

function UserModal({ user, onClose, onSaved }) {
  const isEdit = !!user;
  const [name,     setName]     = useState(user?.name || "");
  const [email,    setEmail]    = useState(user?.email || "");
  const [role,     setRole]     = useState(user?.role || "editor");
  const [password, setPassword] = useState("");
  const [error,    setError]    = useState("");
  const [saving,   setSaving]   = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(""); setSaving(true);
    try {
      if (isEdit) {
        const body = { name, role };
        if (password) body.password = password;
        await axios.put(`/api/auth/users/${user.id}`, body);
      } else {
        if (!password) { setError("Password is required"); setSaving(false); return; }
        await axios.post("/api/auth/users", { email: email.trim(), name, role, password });
      }
      onSaved();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-800">{isEdit ? "Edit User" : "Add User"}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <Field label="Name" type="text" value={name} onChange={setName} placeholder="Full name" />
          {!isEdit && (
            <Field label="Email" type="email" value={email} onChange={setEmail}
              placeholder="user@example.com" required />
          )}
          <div>
            <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5">Role</label>
            <select value={role} onChange={e => setRole(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-400">
              <option value="editor">Editor — can view and edit data</option>
              <option value="viewer">Viewer — read-only</option>
              <option value="admin">Admin — full access + user management</option>
            </select>
          </div>
          <Field label={isEdit ? "New password (leave blank to keep)" : "Password"}
            type="password" value={password} onChange={setPassword}
            placeholder="••••••••" required={!isEdit} />

          {error && <p className="text-red-500 text-sm">{error}</p>}

          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-200 text-gray-600 rounded-lg text-sm hover:bg-gray-50">
              Cancel
            </button>
            <button type="submit" disabled={saving}
              className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-500 disabled:opacity-50">
              {saving ? "Saving…" : isEdit ? "Save Changes" : "Create User"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({ label, type, value, onChange, placeholder, required }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5">{label}</label>
      <input type={type} value={value} onChange={e => onChange(e.target.value)}
        placeholder={placeholder} required={required}
        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700
          focus:outline-none focus:ring-2 focus:ring-indigo-400" />
    </div>
  );
}
