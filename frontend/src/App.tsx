import { useCallback, useEffect, useState } from "react";
import { api, fmtTime, type Member, type Task, type Today } from "./api";
import "./styles.css";

const CATS = ["medicine", "appointment", "checkin", "other"];

function toLocalInput(iso: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${iso.getFullYear()}-${p(iso.getMonth() + 1)}-${p(iso.getDate())}T${p(
    iso.getHours()
  )}:${p(iso.getMinutes())}`;
}

export default function App() {
  const [today, setToday] = useState<Today | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [who, setWho] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [netErr, setNetErr] = useState(false);

  // add-task form
  const [title, setTitle] = useState("");
  const [cat, setCat] = useState("medicine");
  const [due, setDue] = useState(() => toLocalInput(new Date(Date.now() + 3600e3)));
  const [adding, setAdding] = useState(false);

  // assistant
  const [q, setQ] = useState("");
  const [ans, setAns] = useState("");
  const [asking, setAsking] = useState(false);

  const load = useCallback(async () => {
    try {
      const [t, m] = await Promise.all([api.today(), api.members()]);
      setToday(t);
      setMembers(m);
      if (m.length && who === null) setWho(m[0].id);
      setNetErr(false);
    } catch {
      setNetErr(true);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function ensureSeed() {
    await api.seed();
    await load();
  }

  async function addTask() {
    if (!title.trim()) {
      setError("Please enter what needs doing.");
      return;
    }
    setAdding(true);
    setError("");
    try {
      const recips = await api.recipients();
      const rid = recips[0]?.id;
      if (!rid) throw new Error("No care recipient yet — tap Seed demo first.");
      await api.addTask({
        title: title.trim(),
        category: cat,
        due_at: new Date(due).toISOString(),
        recipient_id: rid,
      });
      setTitle("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add task.");
    } finally {
      setAdding(false);
    }
  }

  async function markDone(t: Task) {
    if (who === null) {
      setError("Pick who is doing it first (tap a name).");
      return;
    }
    setError("");
    try {
      await api.complete(t.id, who, t.version);
      await load();
    } catch (e) {
      setError(
        e instanceof Error && e.message.includes("409")
          ? "Someone just marked this — refreshed below."
          : "Could not mark done. The list was refreshed, please try again."
      );
      await load();
    }
  }

  async function ask() {
    if (!q.trim() || asking) return;
    setAsking(true);
    setAns("");
    await api.ask(
      q.trim(),
      (tok) => setAns((a) => a + tok),
      () => setAsking(false),
      () => {
        setAns("Sorry — the assistant is unavailable right now.");
        setAsking(false);
      }
    );
  }

  function taskCard(t: Task, kind: "overdue" | "due" | "done") {
    return (
      <div key={t.id} className={`task ${kind}`}>
        <div className="title">{t.title}</div>
        <div className="meta">
          {t.category} · due {fmtTime(t.due_at)}
        </div>
        {t.status === "done" ? (
          <div className="by">
            ✓ Done{t.completed_by_name ? ` by ${t.completed_by_name}` : ""}
            {t.completed_at ? ` at ${fmtTime(t.completed_at)}` : ""}
          </div>
        ) : (
          <button className="big done" onClick={() => markDone(t)}>
            ✓ Mark done
          </button>
        )}
      </div>
    );
  }

  if (loading) return <div className="wrap">Loading today…</div>;
  if (netErr && !today)
    return (
      <div className="wrap">
        <h1>CareCircle Lite</h1>
        <p>Could not reach the API. Is it running on :8000?</p>
        <button className="big" onClick={load}>
          Retry
        </button>
      </div>
    );

  return (
    <div className="wrap">
      <header className="top">
        <div>
          <h1>Today</h1>
          <p className="sub">
            {today?.date} · {today?.counts.total ?? 0} tasks ·{" "}
            {today?.counts.done ?? 0} done
          </p>
        </div>
        <button className="big ghost" style={{ width: "auto" }} onClick={load}>
          ↻
        </button>
      </header>

      {today?.counts.total === 0 && (
        <div className="card">
          <p className="empty">No tasks yet.</p>
          <button className="big ghost" onClick={ensureSeed}>
            Load demo tasks
          </button>
        </div>
      )}

      <section className="card">
        <h2>
          <span className="badge over">{today?.counts.overdue ?? 0}</span>{" "}
          Overdue — do first
        </h2>
        {today?.overdue.length ? (
          today.overdue.map((t) => taskCard(t, "overdue"))
        ) : (
          <p className="empty">Nothing overdue. 🎉</p>
        )}
      </section>

      <section className="card">
        <h2>
          <span className="badge dueb">{today?.counts.due ?? 0}</span> Due today
        </h2>
        {today?.due.length ? (
          today.due.map((t) => taskCard(t, "due"))
        ) : (
          <p className="empty">Nothing else due.</p>
        )}
      </section>

      <section className="card">
        <h2>
          <span className="badge doneb">{today?.counts.done ?? 0}</span> Done
        </h2>
        {today?.done.length ? (
          today.done.map((t) => taskCard(t, "done"))
        ) : (
          <p className="empty">Nothing done yet today.</p>
        )}
      </section>

      <section className="card">
        <h2>Who is doing it?</h2>
        <div className="who">
          {members.map((m) => (
            <button
              key={m.id}
              className={who === m.id ? "sel" : ""}
              onClick={() => setWho(m.id)}
            >
              {m.name}
            </button>
          ))}
        </div>
        <details>
          <summary>Add a family member</summary>
          <AddMember
            onAdded={async (m) => {
              setMembers((ms) => [...ms, m]);
              setWho(m.id);
            }}
          />
        </details>
      </section>

      <section className="card">
        <h2>Add a task</h2>
        <label>What needs doing?</label>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Evening BP tablet"
        />
        <label>Type</label>
        <select value={cat} onChange={(e) => setCat(e.target.value)}>
          {CATS.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <label>Due when?</label>
        <input
          type="datetime-local"
          value={due}
          onChange={(e) => setDue(e.target.value)}
        />
        <button className="big" disabled={adding} onClick={addTask}>
          {adding ? "Adding…" : "＋ Add task"}
        </button>
        {error && <p className="err">{error}</p>}
      </section>

      <section className="card">
        <h2>Ask about today</h2>
        <div className="row">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder='e.g. "What is still pending?"'
            onKeyDown={(e) => e.key === "Enter" && ask()}
          />
        </div>
        <button className="big" disabled={asking} onClick={ask}>
          {asking ? "Thinking…" : "Ask"}
        </button>
        {(ans || asking) && <p className="answer">{ans || "…"}</p>}
      </section>
    </div>
  );
}

function AddMember({ onAdded }: { onAdded: (m: Member) => void }) {
  const [name, setName] = useState("");
  return (
    <div className="row" style={{ marginTop: 8 }}>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Name, e.g. Meera"
      />
      <button
        className="big"
        style={{ width: "auto" }}
        onClick={async () => {
          if (!name.trim()) return;
          const m = await api.addMember(name.trim());
          setName("");
          onAdded(m);
        }}
      >
        Add
      </button>
    </div>
  );
}
