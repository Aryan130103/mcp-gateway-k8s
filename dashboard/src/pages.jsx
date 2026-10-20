import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

export function SecretBox({ title, value, onClose }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    let ok = false;
    try {
      if (window.isSecureContext && navigator.clipboard) {
        await navigator.clipboard.writeText(value);
        ok = true;
      }
    } catch {
      ok = false;
    }
    if (!ok) {
      const ta = document.createElement("textarea");
      ta.value = value;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { ok = document.execCommand("copy"); } catch { ok = false; }
      document.body.removeChild(ta);
    }
    setCopied(ok ? "yes" : "no");
  }
  return (
    <div className="notice">
      <strong>{title}</strong>
      <div className="mono secret">{value}</div>
      <div className="row">
        <button className="ghost" onClick={copy}>{copied === "yes" ? "Copied" : copied === "no" ? "Select the text, then Ctrl+C" : "Copy"}</button>
        <button className="ghost" onClick={onClose}>I saved it</button>
      </div>
      <div className="muted">Shown once. It cannot be shown again.</div>
    </div>
  );
}

const when = (ts) => new Date(ts.replace(" ", "T") + "Z").toLocaleString();

export function MembersPage() {
  const [users, setUsers] = useState(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ name: "", role: "member" });
  const [formError, setFormError] = useState("");
  const [secret, setSecret] = useState(null);

  const load = useCallback(async () => {
    try {
      setUsers(await api("/api/users"));
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function invite(e) {
    e.preventDefault();
    setFormError("");
    try {
      const r = await api("/api/users", { method: "POST", body: form });
      setSecret({ title: `Temporary password for ${r.name}`, value: r.temporary_password });
      setForm({ name: "", role: "member" });
      await load();
    } catch (err) {
      setFormError(err.message);
    }
  }

  return (
    <>
      {secret && <SecretBox title={secret.title} value={secret.value} onClose={() => setSecret(null)} />}
      <form className="card" onSubmit={invite}>
        <h2>Invite a member</h2>
        <div className="row">
          <input placeholder="name" value={form.name} className="grow"
                 onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
            <option value="member">member</option>
            <option value="admin">admin</option>
          </select>
          <button disabled={!form.name}>Invite</button>
        </div>
        {formError && <div className="error">{formError}</div>}
      </form>
      <div className="card">
        <h2>Members</h2>
        {error && <div className="error">{error}</div>}
        {users && (
          <table>
            <thead><tr><th>Name</th><th>Role</th><th>Created</th></tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}><td><strong>{u.name}</strong></td><td>{u.role}</td><td>{when(u.created_at)}</td></tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

export function KeysPage({ isAdmin }) {
  const [mine, setMine] = useState(null);
  const [all, setAll] = useState(null);
  const [error, setError] = useState("");
  const [label, setLabel] = useState("");
  const [secret, setSecret] = useState(null);

  const load = useCallback(async () => {
    try {
      setMine(await api("/api/me/keys"));
      if (isAdmin) setAll(await api("/api/keys"));
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }, [isAdmin]);
  useEffect(() => { load(); }, [load]);

  async function create(e) {
    e.preventDefault();
    try {
      const r = await api("/api/me/keys", { method: "POST", body: { label: label || "default" } });
      setSecret({ title: "Your new API key", value: r.api_key });
      setLabel("");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function revoke(path) {
    if (!window.confirm("Revoke this key? Clients using it will stop working.")) return;
    try {
      await api(path, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  const status = (k) => (k.revoked_at ? "Revoked" : "Active");

  return (
    <>
      {secret && <SecretBox title={secret.title} value={secret.value} onClose={() => setSecret(null)} />}
      {error && <div className="error">{error}</div>}
      <form className="card" onSubmit={create}>
        <h2>Generate a key</h2>
        <p className="muted">Paste it into Claude Code, Cursor or MCP Inspector with the gateway URL.</p>
        <div className="row">
          <input placeholder="label, e.g. my laptop" value={label} className="grow"
                 onChange={(e) => setLabel(e.target.value)} />
          <button>Generate</button>
        </div>
      </form>
      <div className="card">
        <h2>My keys</h2>
        {mine && (
          <table>
            <thead><tr><th>Label</th><th>Starts with</th><th>Created</th><th>Status</th><th /></tr></thead>
            <tbody>
              {mine.map((k) => (
                <tr key={k.id}>
                  <td>{k.label}</td><td className="mono">{k.prefix}</td><td>{when(k.created_at)}</td>
                  <td><span className={`badge ${k.revoked_at ? "disabled" : "connected"}`}>{status(k)}</span></td>
                  <td className="actions">
                    {!k.revoked_at && <button className="danger" onClick={() => revoke(`/api/me/keys/${k.id}`)}>Revoke</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {isAdmin && all && (
        <div className="card">
          <h2>All keys (admin)</h2>
          <table>
            <thead><tr><th>User</th><th>Label</th><th>Starts with</th><th>Status</th><th /></tr></thead>
            <tbody>
              {all.map((k) => (
                <tr key={k.id}>
                  <td>{k.user}</td><td>{k.label}</td><td className="mono">{k.prefix}</td>
                  <td><span className={`badge ${k.revoked_at ? "disabled" : "connected"}`}>{status(k)}</span></td>
                  <td className="actions">
                    {!k.revoked_at && <button className="danger" onClick={() => revoke(`/api/keys/${k.id}`)}>Revoke</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

export function AuditPage() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      setRows(await api("/api/audit?limit=100"));
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="card">
      <div className="row">
        <h2>Audit log</h2><span className="spacer" />
        <button className="ghost" onClick={load}>Refresh</button>
      </div>
      {error && <div className="error">{error}</div>}
      {rows && rows.length === 0 && <p className="muted">No tool calls yet.</p>}
      {rows && rows.length > 0 && (
        <table>
          <thead><tr><th>When</th><th>User</th><th>Server</th><th>Tool</th><th>Time</th><th>Result</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{when(r.ts)}</td><td>{r.user_name}</td><td>{r.server || "-"}</td>
                <td className="mono">{r.tool}</td><td>{r.duration_ms} ms</td>
                <td>
                  <span className={`badge ${r.outcome === "ok" ? "connected" : "unreachable"}`}>{r.outcome}</span>
                  {r.detail && <span className="muted"> {r.detail}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}


export function ChatPage() {
  const [messages, setMessages] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem("gw_chat")) || []; } catch { return []; }
  });
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [configured, setConfigured] = useState(null);
  const [error, setError] = useState("");
  const endRef = useRef(null);
  useEffect(() => {
    try { sessionStorage.setItem("gw_chat", JSON.stringify(messages)); } catch { /* storage unavailable */ }
  }, [messages]);

  useEffect(() => {
    api("/api/chat/status").then((d) => setConfigured(d.configured)).catch(() => setConfigured(false));
  }, []);
  useEffect(() => {
    if (endRef.current) endRef.current.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function send(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    const next = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setBusy(true);
    setError("");
    try {
      const r = await api("/api/chat", {
        method: "POST",
        body: { messages: next.map(({ role, content }) => ({ role, content })) },
      });
      setMessages([...next, { role: "assistant", content: r.reply, tools: r.tool_calls }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (configured === false) {
    return (
      <div className="card">
        <h2>Chat</h2>
        <p className="muted">Chat isn&apos;t configured: an administrator needs to add an LLM key. Everything else still works.</p>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="row">
        <h2>Chat</h2><span className="spacer" />
        <button className="ghost" onClick={() => setMessages([])}>Clear chat</button>
      </div>
      <p className="muted">Ask about the store. The assistant uses the same tools and permissions as you, and every call is logged.</p>
      <div className="chat">
        {messages.length === 0 && <p className="muted">Try: &quot;What orders came in today?&quot; or &quot;List the products&quot;.</p>}
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            <div className="text">{m.content}</div>
            {m.tools && m.tools.length > 0 && (
              <div className="toolcalls">
                {m.tools.map((t, j) => (
                  <details key={j}>
                    <summary>
                      <span className={`badge ${t.ok ? "connected" : "unreachable"}`}>{t.ok ? "ok" : "error"}</span>{" "}
                      <span className="mono">{t.tool}</span>
                    </summary>
                    <pre className="mono">{JSON.stringify(t.arguments, null, 2)}</pre>
                  </details>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="bubble assistant muted">Thinking...</div>}
        <div ref={endRef} />
      </div>
      {error && <div className="error">{error}</div>}
      <form className="row" onSubmit={send}>
        <input className="grow" placeholder="Ask something..." value={input}
               onChange={(e) => setInput(e.target.value)} disabled={busy} />
        <button disabled={busy || !input.trim()}>Send</button>
      </form>
    </div>
  );
}
