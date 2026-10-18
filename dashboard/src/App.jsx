import { useCallback, useEffect, useState } from "react";
import { api, clearSession, getSession, saveSession } from "./api";
import { AuditPage, KeysPage, MembersPage } from "./pages";

function Login({ onLogin }) {
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const session = await api("/api/login", { method: "POST", body: { name, password } });
      saveSession(session);
      onLogin(session);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center">
      <form className="card login" onSubmit={submit}>
        <h1>MCP Gateway</h1>
        <p className="muted">Sign in to manage servers and keys.</p>
        <label>Name
          <input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </label>
        <label>Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <div className="error">{error}</div>}
        <button disabled={busy || !name || !password}>{busy ? "Signing in..." : "Sign in"}</button>
      </form>
    </div>
  );
}

function StatusBadge({ status }) {
  return <span className={`badge ${status.toLowerCase()}`}>{status}</span>;
}

function ServersPage() {
  const [servers, setServers] = useState(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(null);
  const [form, setForm] = useState({ name: "", url: "" });
  const [formError, setFormError] = useState("");

  const load = useCallback(async () => {
    try {
      setServers(await api("/api/dashboard/servers"));
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, [load]);

  async function run(fn) {
    try {
      await fn();
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  const toggle = (s) =>
    run(() => api(`/api/servers/${s.id}`, { method: "PATCH", body: { enabled: s.status === "Disabled" } }));

  const remove = (s) => {
    if (window.confirm(`Remove server "${s.name}"?`)) {
      run(() => api(`/api/servers/${s.id}`, { method: "DELETE" }));
    }
  };

  async function add(e) {
    e.preventDefault();
    setFormError("");
    try {
      await api("/api/servers", { method: "POST", body: { name: form.name, url: form.url } });
      setForm({ name: "", url: "" });
      await load();
    } catch (err) {
      setFormError(err.message);
    }
  }

  return (
    <>
      <div className="card">
        <div className="row">
          <h2>MCP servers</h2>
          <span className="spacer" />
          <button className="ghost" onClick={load}>Refresh</button>
        </div>
        {error && <div className="error">{error}</div>}
        {servers === null && !error && <p className="muted">Loading (a dead server can take a few seconds)...</p>}
        {servers && (
          <table>
            <thead>
              <tr><th>Name</th><th>URL</th><th>Status</th><th>Tools</th><th /></tr>
            </thead>
            <tbody>
              {servers.map((s) => (
                <>
                  <tr key={s.id} className="clickable" onClick={() => setOpen(open === s.id ? null : s.id)}>
                    <td><strong>{s.name}</strong></td>
                    <td className="mono">{s.url}</td>
                    <td><StatusBadge status={s.status} />{s.error && <span className="muted"> {s.error}</span>}</td>
                    <td>{s.tools.length}</td>
                    <td className="actions" onClick={(e) => e.stopPropagation()}>
                      <button className="ghost" onClick={() => toggle(s)}>
                        {s.status === "Disabled" ? "Enable" : "Disable"}
                      </button>
                      <button className="danger" onClick={() => remove(s)}>Remove</button>
                    </td>
                  </tr>
                  {open === s.id && (
                    <tr key={`${s.id}-tools`}>
                      <td colSpan="5">
                        {s.tools.length === 0 ? (
                          <span className="muted">No tools listed.</span>
                        ) : (
                          <ul className="tools">
                            {s.tools.map((t) => (
                              <li key={t.name}><span className="mono">{s.name}__{t.name}</span>
                                <div className="muted">{(t.description || "").split("\n")[0]}</div></li>
                            ))}
                          </ul>
                        )}
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <form className="card" onSubmit={add}>
        <h2>Add a server</h2>
        <div className="row">
          <input placeholder="name (lowercase letters and digits)" value={form.name}
                 onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input placeholder="http://server:8000/mcp" value={form.url} className="grow"
                 onChange={(e) => setForm({ ...form, url: e.target.value })} />
          <button disabled={!form.name || !form.url}>Add</button>
        </div>
        {formError && <div className="error">{formError}</div>}
      </form>
    </>
  );
}

const TABS = {
  admin: [["servers", "Servers"], ["members", "Members"], ["keys", "API keys"], ["audit", "Audit log"]],
  member: [["keys", "API keys"]],
};

export default function App() {
  const [session, setSession] = useState(getSession());
  const [tab, setTab] = useState(null);
  if (!session) return <Login onLogin={setSession} />;
  const tabs = TABS[session.role] || TABS.member;
  const current = tabs.some(([id]) => id === tab) ? tab : tabs[0][0];
  return (
    <div>
      <header>
        <strong>MCP Gateway</strong>
        <nav className="tabs">
          {tabs.map(([id, label]) => (
            <button key={id} className={id === current ? "tab active" : "tab"} onClick={() => setTab(id)}>{label}</button>
          ))}
        </nav>
        <span className="spacer" />
        <span className="muted">{session.name} ({session.role})</span>
        <button className="ghost" onClick={() => { clearSession(); setSession(null); setTab(null); }}>Sign out</button>
      </header>
      <main>
        {current === "servers" && <ServersPage />}
        {current === "members" && <MembersPage />}
        {current === "keys" && <KeysPage isAdmin={session.role === "admin"} />}
        {current === "audit" && <AuditPage />}
      </main>
    </div>
  );
}
