import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login, user } = useAuth();
  const navigate = useNavigate();

  const [email,     setEmail]     = useState("");
  const [password,  setPassword]  = useState("");
  const [error,     setError]     = useState("");
  const [loading,   setLoading]   = useState(false);
  const [needSetup, setNeedSetup] = useState(false);

  // Setup state
  const [setupName, setSetupName] = useState("");
  const [setupPwd,  setSetupPwd]  = useState("");

  useEffect(() => {
    if (user) { navigate("/home", { replace: true }); return; }
    axios.get("/api/auth/needs-setup")
      .then(r => setNeedSetup(r.data.data.needs_setup))
      .catch(() => {});
  }, [user]);

  async function handleLogin(e) {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      await login(email.trim(), password);
      navigate("/home", { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleSetup(e) {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      const r = await axios.post("/api/auth/setup", {
        email: email.trim(), name: setupName.trim() || "Admin", password: setupPwd,
      });
      const { token, user: u } = r.data.data;
      localStorage.setItem("hid_token", token);
      localStorage.setItem("hid_user",  JSON.stringify(u));
      navigate("/home", { replace: true });
      window.location.reload();
    } catch (err) {
      setError(err.response?.data?.detail || "Setup failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-indigo-600 mb-4">
            <span className="text-white text-2xl font-bold">H</span>
          </div>
          <h1 className="text-2xl font-bold text-white">HiD</h1>
          <p className="text-gray-400 text-sm mt-1">Hotel Intelligence Dashboard</p>
        </div>

        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-6 shadow-2xl">
          {needSetup ? (
            <>
              <h2 className="text-white font-semibold text-lg mb-1">First-time Setup</h2>
              <p className="text-gray-400 text-sm mb-5">Create your admin account to get started.</p>
              <form onSubmit={handleSetup} className="space-y-4">
                <Field label="Your name" type="text" value={setupName}
                  onChange={setSetupName} placeholder="Admin" />
                <Field label="Email" type="email" value={email}
                  onChange={setEmail} placeholder="admin@example.com" required />
                <Field label="Password" type="password" value={setupPwd}
                  onChange={setSetupPwd} placeholder="Min 8 characters" required />
                {error && <p className="text-red-400 text-sm">{error}</p>}
                <button type="submit" disabled={loading}
                  className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50">
                  {loading ? "Creating…" : "Create Admin Account"}
                </button>
              </form>
            </>
          ) : (
            <>
              <h2 className="text-white font-semibold text-lg mb-5">Sign in</h2>
              <form onSubmit={handleLogin} className="space-y-4">
                <Field label="Email" type="email" value={email}
                  onChange={setEmail} placeholder="you@example.com" required />
                <Field label="Password" type="password" value={password}
                  onChange={setPassword} placeholder="••••••••" required />
                {error && <p className="text-red-400 text-sm">{error}</p>}
                <button type="submit" disabled={loading}
                  className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50">
                  {loading ? "Signing in…" : "Sign in"}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, type, value, onChange, placeholder, required }) {
  return (
    <div>
      <label className="block text-gray-400 text-xs font-medium mb-1.5 uppercase tracking-wide">
        {label}
      </label>
      <input type={type} value={value} onChange={e => onChange(e.target.value)}
        placeholder={placeholder} required={required}
        className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm
          placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent" />
    </div>
  );
}
