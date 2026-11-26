import { useCallback, useEffect, useMemo, useState } from "react";
import { api, fmtTime, type Member, type Task, type Today } from "./api";
import { Icon } from "./icons";
import "./styles.css";

type Tab = "today" | "meds" | "activity" | "family";
const CATS = ["medicine", "appointment", "checkin", "other"];
const CAT_ICON: Record<string, string> = {
  medicine: "pill",
  appointment: "calendar",
  checkin: "phone",
  other: "clipboard-list",
};

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}
function toLocalInput(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(
    d.getHours()
  )}:${p(d.getMinutes())}`;
}
function prettyDate(iso: string): string {
  return new Date(iso).toLocaleDateString([], {
    weekday: "long",
    month: "short",
    day: "numeric",
  });
}

export default function App() {
  const [tab, setTab] = useState<Tab>("today");
  const [today, setToday] = useState<Today | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [recipient, setRecipient] = useState("Mum");
  const [who, setWho] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sheet, setSheet] = useState(false);

  const load = useCallback(async () => {
    try {
      const [t, m, r] = await Promise.all([
        api.today(),
        api.members(),
        api.recipients(),
      ]);
      setToday(t);
      setMembers(m);
      if (r[0]) setRecipient(r[0].name);
      setWho((w) => (w === null && m.length ? m[0].id : w));
    } catch {
      /* offline — keep old state */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const counts = today?.counts ?? { overdue: 0, due: 0, done: 0, total: 0 };
  const meds = useMemo(
    () =>
      [...(today?.overdue ?? []), ...(today?.due ?? [])].filter(
        (t) => t.category === "medicine"
      ),
    [today]
  );

  async function act(fn: () => Promise<unknown>, fail: string) {
    setError("");
    try {
      await fn();
      await load();
    } catch {
      setError(fail);
      await load();
    }
  }
  const take = (t: Task) =>
    who === null
      ? setError("Tap your name under “Who's helping?” first.")
      : act(() => api.complete(t.id, who, t.version), "Someone just updated this — refreshed.");
  const later = (t: Task) => act(() => api.snooze(t.id, t.version), "Could not snooze — refreshed.");
  const undo = (t: Task) => act(() => api.reopen(t.id), "Could not reopen — refreshed.");

  if (loading) return <div className="site">Loading…</div>;

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: "today", label: "Today", icon: "home" },
    { id: "meds", label: "Meds", icon: "pill" },
    { id: "activity", label: "Activity", icon: "activity" },
    { id: "family", label: "Family", icon: "users" },
  ];
  const me = members.find((m) => m.id === who)?.name ?? "family";

  return (
    <div className="site">
      <nav className="navbar">
        <span className="brand">
          <span className="brand-mark">
            <Icon name="activity" size={19} />
          </span>
          CareCircle
        </span>
        <div className="topnav">
          {tabs.map((t) => (
            <button key={t.id} className={tab === t.id ? "on" : ""} onClick={() => setTab(t.id)}>
              <span className="ic">
                <Icon name={t.icon} size={17} />
              </span>
              {t.label}
            </button>
          ))}
        </div>
        <div className="nav-right">
          <span className="nav-user">Helping as <b>{me}</b> · for {recipient}</span>
          <div className="avatar">{recipient.slice(0, 1)}</div>
        </div>
      </nav>

      <header className="topbar">
        <div>
          <div className="greet">
            <span className="ic">
              <Icon name="sun" size={16} />
            </span>{" "}
            {greeting()}, <b>{me}</b>
          </div>
          <h1 className="plan">
            {tab === "today"
              ? "Today's Plan"
              : tab === "meds"
              ? "Medications"
              : tab === "activity"
              ? "Activity"
              : "Family"}
          </h1>
          <p className="date-line">
            {today ? prettyDate(today.date + "T12:00:00") : ""}
          </p>
        </div>
      </header>

      {tab === "today" && (
        <TodayTab
          today={today}
          counts={counts}
          meds={meds}
          members={members}
          who={who}
          setWho={setWho}
          take={take}
          later={later}
          undo={undo}
          error={error}
          reload={load}
        />
      )}
      {tab === "meds" && (
        <MedsTab today={today} take={take} later={later} />
      )}
      {tab === "activity" && <ActivityTab today={today} />}
      {tab === "family" && (
        <FamilyTab members={members} today={today} reload={load} />
      )}

      <button className="fab" onClick={() => setSheet(true)} aria-label="Add task">
        <Icon name="plus" size={28} />
      </button>
      {sheet && <AddSheet close={() => setSheet(false)} reload={load} />}

      <nav className="tabbar">
        {tabs.map((t) => (
          <button key={t.id} className={tab === t.id ? "on" : ""} onClick={() => setTab(t.id)}>
            <span className="ico">
              <Icon name={t.icon} size={22} />
            </span>
            {t.label}
          </button>
        ))}
      </nav>

      <footer className="site-foot">
        <span className="ic">
          <Icon name="heart" size={15} />
        </span>{" "}
        CareCircle Lite · one shared place for {recipient}'s care
      </footer>
    </div>
  );
}

/* ================= Today ================= */

function ProgressCard({ counts }: { counts: { overdue: number; due: number; done: number; total: number } }) {
  const pct = counts.total ? Math.round((counts.done / counts.total) * 100) : 0;
  return (
    <section className="card">
      <div className="prog-top">
        <span className="prog-label">
          <span className="ic">
            <Icon name="sparkles" size={17} />
          </span>{" "}
          Daily Progress
        </span>
        <span className="prog-pct">{counts.done}/{counts.total} · {pct}% done</span>
      </div>
      <div className="bar">
        <i style={{ width: `${pct}%` }} />
      </div>
      <div className="stats">
        <div>
          <div className="n red">{counts.overdue}</div>
          <div className="l">Overdue</div>
        </div>
        <div>
          <div className="n amber">{counts.due}</div>
          <div className="l">Due today</div>
        </div>
        <div>
          <div className="n green">{counts.done}</div>
          <div className="l">Done</div>
        </div>
      </div>
    </section>
  );
}

function MedCard({
  t,
  take,
  later,
}: {
  t: Task;
  take: (t: Task) => void;
  later: (t: Task) => void;
}) {
  const over = t.status !== "done" && new Date(t.due_at).getTime() < Date.now();
  if (t.status === "done")
    return (
      <div className="med done">
        <div className="pill-ico med-ico">
          <Icon name={CAT_ICON[t.category] ?? "clipboard-list"} size={22} />
        </div>
        <div className="med-body">
          <div className="med-name">{t.title}</div>
          <div className="med-meta">
            {t.category} · was due {fmtTime(t.due_at)}
          </div>
          <span className="chip-taken">
            Taken{t.completed_by_name ? ` · ${t.completed_by_name}` : ""}
          </span>
        </div>
      </div>
    );
  return (
    <div className={`med${over ? " overdue" : ""}`}>
      <div className="time-rail">
        <div className="t">{fmtTime(t.due_at)}</div>
      </div>
      <div className="med-body">
        <div className="med-name">{t.title}</div>
        <div className="med-meta">
          {t.category}
          {t.notes ? ` · ${t.notes}` : ""}
        </div>
        <div className="actions">
          <button className="btn-taken" onClick={() => take(t)}>
            <span className="ic">
              <Icon name="check" size={16} />
            </span>{" "}
            Taken
          </button>
          <button className="btn-later" onClick={() => later(t)}>
            <span className="ic">
              <Icon name="clock" size={16} />
            </span>{" "}
            Later
          </button>
        </div>
      </div>
    </div>
  );
}

function TodayTab(props: {
  today: Today | null;
  counts: { overdue: number; due: number; done: number; total: number };
  meds: Task[];
  members: Member[];
  who: number | null;
  setWho: (id: number) => void;
  take: (t: Task) => void;
  later: (t: Task) => void;
  undo: (t: Task) => void;
  error: string;
  reload: () => void;
}) {
  const { today, counts, meds, members, who, setWho, take, later, undo, error, reload } = props;
  const others = useMemo(
    () =>
      [...(today?.overdue ?? []), ...(today?.due ?? [])].filter(
        (t) => t.category !== "medicine"
      ),
    [today]
  );
  return (
    <>
      {counts.total === 0 && (
        <div className="card">
          <p className="empty">No tasks yet — add one with the + button below.</p>
          <button className="btn-ghost" onClick={() => api.seed().then(reload)}>
            Load demo tasks
          </button>
        </div>
      )}

      <div className="cols cols-2">
        <div>
          <div className="sec-head">
            <h2>
              <span className="ic">
                <Icon name="pill" size={18} />
              </span>{" "}
              Medications Today
            </h2>
          </div>
          {meds.length ? (
            meds.map((t) => <MedCard key={t.id} t={t} take={take} later={later} />)
          ) : (
            <p className="empty">No medicines pending.</p>
          )}

          <div className="sec-head">
            <h2>
              <span className="ic">
                <Icon name="clipboard-list" size={18} />
              </span>{" "}
              Other Tasks
            </h2>
          </div>
          {others.length ? (
            others.map((t) => <TaskRow key={t.id} t={t} take={take} />)
          ) : (
            <p className="empty">Nothing else pending.</p>
          )}

          <div className="sec-head">
            <h2>
              <span className="ic">
                <Icon name="circle-check" size={18} />
              </span>{" "}
              Done today
            </h2>
          </div>
          {today?.done.length ? (
            today.done.map((t) => (
              <div key={t.id} className="trow done">
                <button className="check on" onClick={() => undo(t)} aria-label="Reopen" title="Tap to reopen">
                  <Icon name="check" size={16} />
                </button>
                <div>
                  <div className="tt">{t.title}</div>
                  <div className="byline">
                    {t.completed_by_name ? `by ${t.completed_by_name}` : ""}
                    {t.completed_at ? ` · ${fmtTime(t.completed_at)}` : ""} · tap check to undo
                  </div>
                </div>
              </div>
            ))
          ) : (
            <p className="empty">Nothing done yet today.</p>
          )}
        </div>

        <div className="aside">
          <ProgressCard counts={counts} />
          <div className="sec-head">
            <h2>
              <span className="ic">
                <Icon name="users" size={18} />
              </span>{" "}
              Who's helping?
            </h2>
          </div>
          <div className="card">
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
          </div>
          <AskBox />
          {error && <p className="err">{error}</p>}
        </div>
      </div>
    </>
  );
}

function TaskRow({ t, take }: { t: Task; take: (t: Task) => void }) {
  const over = new Date(t.due_at).getTime() < Date.now();
  return (
    <div className={`trow${over ? " overdue" : ""}`}>
      <button className="check" onClick={() => take(t)} aria-label="Mark done">
        <Icon name="check" size={16} />
      </button>
      <div>
        <div className="tt">{t.title}</div>
        <div className="med-meta">
          <span className="ic">
            <Icon name={CAT_ICON[t.category] ?? "clipboard-list"} size={14} />
          </span>{" "}
          {fmtTime(t.due_at)}
        </div>
      </div>
      <span className={`tag${over ? " red" : " amber"}`}>{over ? "Overdue" : "Due"}</span>
    </div>
  );
}

/* ================= Meds tab ================= */

function Ring({ done, total }: { done: number; total: number }) {
  const R = 34;
  const C = 2 * Math.PI * R;
  const frac = total ? done / total : 0;
  return (
    <div className="ring-wrap">
      <svg width="88" height="88" viewBox="0 0 88 88">
        <circle cx="44" cy="44" r={R} fill="none" stroke="#e8e8ed" strokeWidth="10" />
        <circle
          cx="44" cy="44" r={R} fill="none" stroke="#34c759" strokeWidth="10"
          strokeLinecap="round" strokeDasharray={C}
          strokeDashoffset={C * (1 - frac)} transform="rotate(-90 44 44)"
        />
        <text x="44" y="50" textAnchor="middle" fontSize="20" fontWeight="800" fill="#10231c">
          {done}/{total}
        </text>
      </svg>
      <div className="ring-num">
        <b>{total ? Math.round(frac * 100) : 0}%</b>
        <br />
        doses taken today
      </div>
    </div>
  );
}

function MedsTab({
  today,
  take,
  later,
}: {
  today: Today | null;
  take: (t: Task) => void;
  later: (t: Task) => void;
}) {
  const all = useMemo(
    () =>
      [...(today?.overdue ?? []), ...(today?.due ?? []), ...(today?.done ?? [])].filter(
        (t) => t.category === "medicine"
      ),
    [today]
  );
  const done = all.filter((t) => t.status === "done").length;
  return (
    <>
      <section className="card">
        <div className="prog-top">
          <span className="prog-label">TODAY'S ADHERENCE</span>
        </div>
        <div style={{ marginTop: 10 }}>
          <Ring done={done} total={all.length} />
        </div>
      </section>
      {all.length ? (
        <div className="cards-2">
          {all.map((t) => <MedCard key={t.id} t={t} take={take} later={later} />)}
        </div>
      ) : (
        <p className="empty">No medications scheduled.</p>
      )}
    </>
  );
}

/* ================= Activity tab ================= */

function ActivityTab({ today }: { today: Today | null }) {
  const done = today?.done ?? [];
  return (
    <div className="narrow">
      <section className="card">
        <div className="prog-top">
          <span className="prog-label">
            <span className="ic">
              <Icon name="circle-check" size={17} />
            </span>{" "}
            Done today ({done.length})
          </span>
        </div>
        {done.length ? (
          <div className="tl">
            {done.map((t) => (
              <div key={t.id} className="tl-item">
                <span className="tl-dot">
                  <Icon name="check" size={11} />
                </span>
                <div className="tt">{t.title}</div>
                <div className="ts">
                  {t.completed_at ? fmtTime(t.completed_at) : fmtTime(t.due_at)}
                  {t.completed_by_name ? ` · by ${t.completed_by_name}` : ""}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="empty">Nothing done yet — tasks you complete will appear here.</p>
        )}
      </section>
      {(today?.overdue.length ?? 0) > 0 && (
        <section className="card">
          <div className="prog-top">
            <span className="prog-label overdue-label">
              <span className="ic">
                <Icon name="triangle-alert" size={17} />
              </span>{" "}
              Still overdue ({today?.overdue.length})
            </span>
          </div>
          {today?.overdue.map((t) => (
            <div key={t.id} className="tl-item">
              <div className="tt">{t.title}</div>
              <div className="ts">was due {fmtTime(t.due_at)}</div>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

/* ================= Family tab ================= */

function FamilyTab({
  members,
  today,
  reload,
}: {
  members: Member[];
  today: Today | null;
  reload: () => void;
}) {
  const [name, setName] = useState("");
  const doneBy = useMemo(() => {
    const m: Record<number, number> = {};
    for (const t of today?.done ?? [])
      if (t.completed_by_id) m[t.completed_by_id] = (m[t.completed_by_id] ?? 0) + 1;
    return m;
  }, [today]);
  return (
    <div className="narrow">
      {members.map((m) => (
        <div key={m.id} className="fam-row">
          <div className="fam-av">{m.name.slice(0, 1)}</div>
          <div>
            <div className="fam-name">{m.name}</div>
            <div className="fam-sub">{m.relation || "Family"}</div>
          </div>
          <span className="count-badge">{doneBy[m.id] ?? 0} done today</span>
        </div>
      ))}
      <section className="card">
        <div className="prog-top">
          <span className="prog-label">
            <span className="ic">
              <Icon name="plus" size={17} />
            </span>{" "}
            Add family member
          </span>
        </div>
        <div className="ask-row" style={{ marginTop: 10 }}>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name, e.g. Meera"
          />
          <button
            className="ask-go"
            onClick={async () => {
              if (!name.trim()) return;
              await api.addMember(name.trim());
              setName("");
              await reload();
            }}
          >
            Add
          </button>
        </div>
      </section>
    </div>
  );
}

/* ================= Ask ================= */

function AskBox() {
  const [q, setQ] = useState("");
  const [ans, setAns] = useState("");
  const [asking, setAsking] = useState(false);
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
  return (
    <section className="card">
      <div className="prog-top">
        <span className="prog-label">
          <span className="ic">
            <Icon name="message-circle" size={17} />
          </span>{" "}
          Ask about today
        </span>
      </div>
      <div className="ask-row" style={{ marginTop: 10 }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder='e.g. "What is still pending?"'
          onKeyDown={(e) => e.key === "Enter" && ask()}
        />
        <button className="ask-go" disabled={asking} onClick={ask}>
          {asking ? "Thinking" : "Ask"}
        </button>
      </div>
      {(ans || asking) && <p className="answer">{ans || "Thinking…"}</p>}
    </section>
  );
}

/* ================= Add sheet ================= */

function AddSheet({ close, reload }: { close: () => void; reload: () => void }) {
  const [title, setTitle] = useState("");
  const [cat, setCat] = useState("medicine");
  const [due, setDue] = useState(() => toLocalInput(new Date(Date.now() + 3600e3)));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  async function save() {
    if (!title.trim()) {
      setErr("Please enter what needs doing.");
      return;
    }
    setBusy(true);
    try {
      const r = await api.recipients();
      if (!r[0]) {
        await api.seed();
      }
      const recips = await api.recipients();
      await api.addTask({
        title: title.trim(),
        category: cat,
        due_at: new Date(due).toISOString(),
        recipient_id: recips[0].id,
      });
      await reload();
      close();
    } catch {
      setErr("Could not add task — try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="sheet-bg" onClick={close}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="grip" />
        <div className="sheet-head">
          <span className="prog-label" style={{ fontSize: 19 }}>
            <span className="ic">
              <Icon name="plus" size={19} />
            </span>{" "}
            Add a task
          </span>
          <button className="icon-btn" onClick={close} aria-label="Close">
            <Icon name="x" size={20} />
          </button>
        </div>
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
        <input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
        <button className="btn-primary" disabled={busy} onClick={save}>
          {busy ? "Adding…" : "Add task"}
        </button>
        {err && <p className="err">{err}</p>}
      </div>
    </div>
  );
}
