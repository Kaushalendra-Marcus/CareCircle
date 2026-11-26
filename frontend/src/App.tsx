import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, fmtTime, relTime, type Member, type Task, type Today } from "./api";
import { Icon } from "./icons";
import "./styles.css";

type Tab = "today" | "meds" | "activity" | "family";
const TYPES = ["medication", "appointment", "checkin", "general", "other"];
const TYPE_ICON: Record<string, string> = {
  medication: "pill",
  appointment: "calendar",
  checkin: "phone",
  general: "clipboard-list",
  other: "clipboard-list",
};
const PROMPTS = [
  "What's still pending?",
  "Any overdue tasks?",
  "Summarize today.",
  "Did anyone give the morning medicine?",
];

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
function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

/* ================= App ================= */

export default function App() {
  const [tab, setTab] = useState<Tab>("today");
  const [today, setToday] = useState<Today | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [recipient, setRecipient] = useState("Mum");
  const [who, setWho] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [netErr, setNetErr] = useState(false);
  const [sheet, setSheet] = useState<null | { editing?: Task }>(null);
  const [menu, setMenu] = useState(false);
  const [toast, setToast] = useState("");
  const toastTimer = useRef<number | null>(null);

  const say = useCallback((msg: string) => {
    setToast(msg);
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(""), 2600);
  }, []);

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
      setNetErr(false);
    } catch {
      setNetErr(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const counts = today?.summary ?? { total: 0, completed: 0, pending: 0, overdue: 0 };
  const dueCount = counts.pending - counts.overdue;
  const meds = useMemo(
    () =>
      [...(today?.overdue ?? []), ...(today?.due ?? [])].filter(
        (t) => t.task_type === "medication"
      ),
    [today]
  );
  const me = members.find((m) => m.id === who)?.name ?? "family";

  async function act(fn: () => Promise<unknown>, ok: string, fail: string) {
    try {
      await fn();
      await load();
      say(ok);
    } catch {
      await load();
      say(fail);
    }
  }
  const needWho = () => {
    if (who === null) {
      say("Tap your name under Who's helping first.");
      return false;
    }
    return true;
  };
  const take = (t: Task) =>
    needWho() &&
    act(
      () => api.complete(t.id, who, t.version),
      `Done — ${t.title}`,
      "Someone just updated this; refreshed."
    );
  const later = (t: Task) =>
    act(() => api.snooze(t.id, t.version), "Snoozed by 2 hours.", "Could not snooze; refreshed.");
  const undo = (t: Task) =>
    act(() => api.reopen(t.id), "Moved back to due.", "Could not reopen; refreshed.");
  const remove = (t: Task) =>
    act(() => api.removeTask(t.id), "Task deleted.", "Could not delete; refreshed.");

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: "today", label: "Today", icon: "home" },
    { id: "meds", label: "Meds", icon: "pill" },
    { id: "activity", label: "Activity", icon: "activity" },
    { id: "family", label: "Family", icon: "users" },
  ];
  const go = (t: Tab) => {
    setTab(t);
    setMenu(false);
  };

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
            <button key={t.id} className={tab === t.id ? "on" : ""} onClick={() => go(t.id)}>
              {t.label}
            </button>
          ))}
        </div>
        <div className="nav-right">
          <button className="btn-solid-sm" onClick={() => setSheet({})}>
            <span className="ic">
              <Icon name="plus" size={15} />
            </span>
            Add task
          </button>
          <button
            className={`menu-toggle${menu ? " open" : ""}`}
            onClick={() => setMenu((m) => !m)}
            aria-expanded={menu}
            aria-label="Menu"
          >
            <span />
            <span />
          </button>
        </div>
      </nav>
      {menu && (
        <div className="mobile-menu">
          {tabs.map((t) => (
            <button key={t.id} className={tab === t.id ? "on" : ""} onClick={() => go(t.id)}>
              <span className="ic">
                <Icon name={t.icon} size={19} />
              </span>
              {t.label}
            </button>
          ))}
        </div>
      )}

      <header className="topbar">
        {tab === "today" ? (
          <Hero recipient={recipient} me={me} members={members} counts={counts} onAdd={() => setSheet({})} />
        ) : (
          <div>
            <p className="hero-eyebrow">
              CareCircle for <b>{recipient}</b>
            </p>
            <h1 className="plan">
              {tab === "meds" ? "Medications." : tab === "activity" ? "Activity." : "Family."}
            </h1>
            <p className="date-line">
              {tab === "meds"
                ? "Every dose for today, with adherence as you go."
                : tab === "activity"
                ? "Everything the family completed today."
                : "Everyone sharing the care."}{" "}
              {today ? prettyDate(today.date + "T12:00:00") : ""}
            </p>
          </div>
        )}
      </header>

      {loading ? (
        <Skeleton />
      ) : netErr && !today ? (
        <div className="card">
          <p>Could not reach the API. Is it running?</p>
          <button className="btn-primary" onClick={load}>
            Retry
          </button>
        </div>
      ) : (
        <>
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
              remove={remove}
              onEdit={(t) => setSheet({ editing: t })}
              reload={load}
              say={say}
            />
          )}
          {tab === "meds" && <MedsTab today={today} take={take} later={later} remove={remove} onEdit={(t) => setSheet({ editing: t })} />}
          {tab === "activity" && <ActivityTab today={today} />}
          {tab === "family" && <FamilyTab members={members} today={today} reload={load} say={say} setWho={setWho} go={go} />}
        </>
      )}

      <button className="fab" onClick={() => setSheet({})} aria-label="Add task">
        <Icon name="plus" size={28} />
      </button>
      {sheet && (
        <TaskSheet
          editing={sheet.editing}
          members={members}
          close={() => setSheet(null)}
          reload={load}
          say={say}
        />
      )}

      <nav className="tabbar">
        {tabs.map((t) => (
          <button key={t.id} className={tab === t.id ? "on" : ""} onClick={() => go(t.id)}>
            <span className="ico">
              <Icon name={t.icon} size={22} />
            </span>
            {t.label}
          </button>
        ))}
      </nav>

      <footer className="site-foot">
        <div className="foot-grid">
          <div>
            <div className="foot-brand">
              <span className="brand-mark" style={{ width: 26, height: 26 }}>
                <Icon name="activity" size={15} />
              </span>
              CareCircle
            </div>
            <p className="foot-tag">Care is easier when everyone is in the loop.</p>
          </div>
          <div className="foot-col">
            <p className="foot-h">Care</p>
            {tabs.map((t) => (
              <button key={t.id} onClick={() => go(t.id)}>
                {t.label}
              </button>
            ))}
          </div>
          <div className="foot-col">
            <p className="foot-h">Family</p>
            {members.map((m) => (
              <button key={m.id} onClick={() => { setWho(m.id); go("today"); }}>
                {m.name}
              </button>
            ))}
          </div>
          <div className="foot-col">
            <p className="foot-h">Today</p>
            <button onClick={() => go("today")}>
              {counts.completed} of {counts.total} done
            </button>
            <button onClick={() => go("activity")}>{counts.overdue} overdue</button>
          </div>
        </div>
        <div className="foot-base">
          <span>© 2026 CareCircle Lite</span>
          <span>
            {today ? prettyDate(today.date + "T12:00:00") : ""} · for {recipient}
          </span>
        </div>
      </footer>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

/* ================= Hero ================= */

function Hero({
  recipient,
  me,
  members,
  counts,
  onAdd,
}: {
  recipient: string;
  me: string;
  members: Member[];
  counts: { overdue: number; pending: number; completed: number; total: number };
  onAdd: () => void;
}) {
  const dueCount = counts.pending - counts.overdue;
  return (
    <section className="hero">
      <div className="hero-grid">
        <div className="hero-copy">
          <p className="hero-eyebrow">CareCircle Lite · Demo mode</p>
          <h1 className="hero-title">
            {greeting()}, {me}. Let's take care of {recipient}'s day.
          </h1>
          <p className="hero-sub">
            <b>
              {counts.completed} done · {dueCount} to go
              {counts.overdue > 0 ? ` · ${counts.overdue} overdue` : ""}
            </b>{" "}
            — medicines, appointments and check-ins, with who did what.
          </p>
          <div className="hero-ctas">
            <button className="btn-solid-sm btn-lg" onClick={onAdd}>
              <span className="ic">
                <Icon name="plus" size={16} />
              </span>
              Add a task
            </button>
            <button
              className="btn-ghost btn-lg"
              style={{ width: "auto", marginTop: 0 }}
              onClick={() => document.getElementById("plan")?.scrollIntoView({ behavior: "smooth" })}
            >
              See today's plan
            </button>
          </div>
          <div className="hero-stats">
            <div>
              <div className="n red">{counts.overdue}</div>
              <div className="l">Overdue</div>
            </div>
            <div>
              <div className="n amber">{dueCount}</div>
              <div className="l">Due today</div>
            </div>
            <div>
              <div className="n green">{counts.completed}</div>
              <div className="l">Done</div>
            </div>
            <div>
              <div className="n">{members.length}</div>
              <div className="l">Helping</div>
            </div>
          </div>
        </div>
        <div className="hero-img">
          <img
            src="/images/hero-hands.jpg"
            alt="A family member gently holding their parent's hand in warm sunlight"
          />
        </div>
      </div>
    </section>
  );
}

/* ================= Skeleton ================= */

function Skeleton() {
  return (
    <div aria-label="Loading">
      {[0, 1, 2].map((i) => (
        <div key={i} className="card skel">
          <div className="skel-line w60" />
          <div className="skel-line" />
          <div className="skel-line w40" />
        </div>
      ))}
    </div>
  );
}

/* ================= Today ================= */

function ProgressCard({ counts }: { counts: { overdue: number; pending: number; completed: number; total: number } }) {
  const due = counts.pending - counts.overdue;
  const pct = counts.total ? Math.round((counts.completed / counts.total) * 100) : 0;
  return (
    <section className="card">
      <div className="prog-top">
        <span className="prog-label">
          <span className="ic">
            <Icon name="sparkles" size={17} />
          </span>{" "}
          Daily Progress
        </span>
        <span className="prog-pct">
          {counts.completed}/{counts.total} · {pct}%
        </span>
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
          <div className="n amber">{due}</div>
          <div className="l">Due today</div>
        </div>
        <div>
          <div className="n green">{counts.completed}</div>
          <div className="l">Done</div>
        </div>
      </div>
    </section>
  );
}

function CardActions({
  t,
  take,
  later,
  remove,
  onEdit,
}: {
  t: Task;
  take: (t: Task) => void;
  later: (t: Task) => void;
  remove: (t: Task) => void;
  onEdit: (t: Task) => void;
}) {
  const [confirm, setConfirm] = useState(false);
  return (
    <>
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
      <div className="row-actions">
        <button className="mini-btn" onClick={() => onEdit(t)}>
          <span className="ic">
            <Icon name="pencil" size={14} />
          </span>{" "}
          Edit
        </button>
        {confirm ? (
          <>
            <button className="mini-btn danger" onClick={() => remove(t)}>
              Confirm delete
            </button>
            <button className="mini-btn" onClick={() => setConfirm(false)}>
              Keep
            </button>
          </>
        ) : (
          <button className="mini-btn" onClick={() => setConfirm(true)}>
            <span className="ic">
              <Icon name="trash" size={14} />
            </span>{" "}
            Delete
          </button>
        )}
      </div>
    </>
  );
}

function MedCard(props: {
  t: Task;
  take: (t: Task) => void;
  later: (t: Task) => void;
  remove: (t: Task) => void;
  onEdit: (t: Task) => void;
}) {
  const { t, take, later, remove, onEdit } = props;
  const over = t.status !== "completed" && new Date(t.due_at).getTime() < Date.now();
  if (t.status === "completed")
    return (
      <div className="med done">
        <div className="pill-ico med-ico">
          <Icon name={TYPE_ICON[t.task_type] ?? "clipboard-list"} size={22} />
        </div>
        <div className="med-body">
          <div className="med-name">{t.title}</div>
          <div className="med-meta">
            {t.task_type} · was due {fmtTime(t.due_at)}
          </div>
          <span className="chip-taken">
            Taken{t.completed_by_name ? ` · ${t.completed_by_name}` : ""}
            {t.completed_at ? ` · ${relTime(t.completed_at)}` : ""}
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
          {t.task_type}
          {t.description ? ` · ${t.description}` : ""}
          {t.assigned_member_name ? ` · for ${t.assigned_member_name}` : ""}
        </div>
        <CardActions t={t} take={take} later={later} remove={remove} onEdit={onEdit} />
      </div>
    </div>
  );
}

function TaskRow({
  t,
  take,
  remove,
  onEdit,
}: {
  t: Task;
  take: (t: Task) => void;
  remove: (t: Task) => void;
  onEdit: (t: Task) => void;
}) {
  const over = new Date(t.due_at).getTime() < Date.now();
  const [confirm, setConfirm] = useState(false);
  return (
    <div className={`trow${over ? " overdue" : ""}`}>
      <button className="check" onClick={() => take(t)} aria-label={`Mark ${t.title} done`}>
        <Icon name="check" size={16} />
      </button>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="tt">{t.title}</div>
        <div className="med-meta">
          <span className="ic">
            <Icon name={TYPE_ICON[t.task_type] ?? "clipboard-list"} size={14} />
          </span>{" "}
          {fmtTime(t.due_at)}
          {t.assigned_member_name ? ` · for ${t.assigned_member_name}` : ""}
        </div>
        <div className="row-actions">
          <button className="mini-btn" onClick={() => onEdit(t)}>
            Edit
          </button>
          {confirm ? (
            <>
              <button className="mini-btn danger" onClick={() => remove(t)}>
                Confirm delete
              </button>
              <button className="mini-btn" onClick={() => setConfirm(false)}>
                Keep
              </button>
            </>
          ) : (
            <button className="mini-btn" onClick={() => setConfirm(true)}>
              Delete
            </button>
          )}
        </div>
      </div>
      <span className={`tag${over ? " red" : " amber"}`}>{over ? "Overdue" : "Due"}</span>
    </div>
  );
}

function TodayTab(props: {
  today: Today | null;
  counts: { overdue: number; pending: number; completed: number; total: number };
  meds: Task[];
  members: Member[];
  who: number | null;
  setWho: (id: number) => void;
  take: (t: Task) => void;
  later: (t: Task) => void;
  undo: (t: Task) => void;
  remove: (t: Task) => void;
  onEdit: (t: Task) => void;
  reload: () => void;
  say: (m: string) => void;
}) {
  const { today, counts, meds, members, who, setWho, take, later, undo, remove, onEdit, reload, say } = props;
  const others = useMemo(
    () =>
      [...(today?.overdue ?? []), ...(today?.due ?? [])].filter(
        (t) => t.task_type !== "medication"
      ),
    [today]
  );
  return (
    <>
      {counts.total === 0 && (
        <div className="card">
          <p className="empty">No tasks yet — add one with the button above.</p>
          <button
            className="btn-ghost"
            onClick={() => api.seed().then(() => { reload(); say("Demo tasks loaded."); })}
          >
            Load demo tasks
          </button>
        </div>
      )}

      <div className="cols cols-2" id="plan">
        <div>
          <div className="sec-head">
            <h2>
              <span className="ic">
                <Icon name="pill" size={18} />
              </span>{" "}
              Medications Today ({meds.length})
            </h2>
          </div>
          {meds.length ? (
            meds.map((t) => <MedCard key={t.id} t={t} take={take} later={later} remove={remove} onEdit={onEdit} />)
          ) : (
            <p className="empty">No medicines pending.</p>
          )}

          <div className="sec-head">
            <h2>
              <span className="ic">
                <Icon name="clipboard-list" size={18} />
              </span>{" "}
              Other Tasks ({others.length})
            </h2>
          </div>
          {others.length ? (
            others.map((t) => <TaskRow key={t.id} t={t} take={take} remove={remove} onEdit={onEdit} />)
          ) : (
            <p className="empty">Nothing else pending.</p>
          )}

          <div className="sec-head">
            <h2>
              <span className="ic">
                <Icon name="circle-check" size={18} />
              </span>{" "}
              Done today ({today?.done.length ?? 0})
            </h2>
          </div>
          {today?.done.length ? (
            today.done.map((t) => (
              <div key={t.id} className="trow done">
                <button className="check on" onClick={() => undo(t)} aria-label={`Reopen ${t.title}`} title="Tap to reopen">
                  <Icon name="check" size={16} />
                </button>
                <div>
                  <div className="tt">{t.title}</div>
                  <div className="byline">
                    {t.completed_by_name ? `by ${t.completed_by_name}` : ""}
                    {t.completed_at ? ` · ${relTime(t.completed_at)}` : ""} · tap check to undo
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
                <button key={m.id} className={who === m.id ? "sel" : ""} onClick={() => setWho(m.id)}>
                  {m.name}
                </button>
              ))}
            </div>
            <p className="demo-note">Demo mode — no login. Your pick is recorded on every task you complete.</p>
          </div>
          <AskBox say={say} />
        </div>
      </div>
    </>
  );
}

/* ================= Meds tab ================= */

function Ring({ done, total }: { done: number; total: number }) {
  const R = 34;
  const C = 2 * Math.PI * R;
  const frac = total ? done / total : 0;
  return (
    <div className="ring-wrap">
      <svg width="88" height="88" viewBox="0 0 88 88" role="img" aria-label={`${done} of ${total} doses taken`}>
        <circle cx="44" cy="44" r={R} fill="none" stroke="#e8e8ed" strokeWidth="10" />
        <circle
          cx="44" cy="44" r={R} fill="none" stroke="#34c759" strokeWidth="10"
          strokeLinecap="round" strokeDasharray={C}
          strokeDashoffset={C * (1 - frac)} transform="rotate(-90 44 44)"
        />
        <text x="44" y="50" textAnchor="middle" fontSize="20" fontWeight="700" fill="#1d1d1f">
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
  remove,
  onEdit,
}: {
  today: Today | null;
  take: (t: Task) => void;
  later: (t: Task) => void;
  remove: (t: Task) => void;
  onEdit: (t: Task) => void;
}) {
  const all = useMemo(
    () =>
      [...(today?.overdue ?? []), ...(today?.due ?? []), ...(today?.done ?? [])].filter(
        (t) => t.task_type === "medication"
      ),
    [today]
  );
  const done = all.filter((t) => t.status === "completed").length;
  return (
    <>
      <section className="feature">
        <img src="/images/meds-pills.jpg" alt="Colorful daily medication pills and capsules" />
        <div className="feature-copy">
          <h2>Medicines, on time, every time.</h2>
          <p>
            Every dose for today in one list. Tap Taken when it's done, or
            Later to snooze it by two hours — the family sees it all.
          </p>
        </div>
      </section>
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
          {all.map((t) => <MedCard key={t.id} t={t} take={take} later={later} remove={remove} onEdit={onEdit} />)}
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
                  {t.completed_at ? relTime(t.completed_at) : fmtTime(t.due_at)}
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
  say,
  setWho,
  go,
}: {
  members: Member[];
  today: Today | null;
  reload: () => void;
  say: (m: string) => void;
  setWho: (id: number) => void;
  go: (t: Tab) => void;
}) {
  const [name, setName] = useState("");
  const doneBy = useMemo(() => {
    const m: Record<number, number> = {};
    for (const t of today?.done ?? [])
      if (t.completed_by_member_id) m[t.completed_by_member_id] = (m[t.completed_by_member_id] ?? 0) + 1;
    return m;
  }, [today]);
  return (
    <div className="narrow">
      <section className="feature flip">
        <img src="/images/care-call.jpg" alt="A doctor coordinating care over the phone" />
        <div className="feature-copy">
          <h2>One family, one place.</h2>
          <p>
            No more "who gave the evening medicine?" over calls and chats —
            every dose and task shows who did it and when.
          </p>
        </div>
      </section>
      {members.map((m) => (
        <button key={m.id} className="fam-row as-btn" onClick={() => { setWho(m.id); go("today"); say(`Helping as ${m.name}.`); }}>
          <div className="fam-av">{m.name.slice(0, 1)}</div>
          <div style={{ textAlign: "left" }}>
            <div className="fam-name">{m.name}</div>
            <div className="fam-sub">{m.relationship || "Family"}</div>
          </div>
          <span className="count-badge">{doneBy[m.id] ?? 0} done today</span>
        </button>
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
            aria-label="Family member name"
          />
          <button
            className="ask-go"
            onClick={async () => {
              if (!name.trim()) return;
              await api.addMember(name.trim());
              setName("");
              await reload();
              say("Family member added.");
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

function AskBox({ say }: { say: (m: string) => void }) {
  const [q, setQ] = useState("");
  const [ans, setAns] = useState("");
  const [asking, setAsking] = useState(false);
  const [interactionId, setInteractionId] = useState<number | null>(null);
  const abort = useRef<AbortController | null>(null);

  async function ask(question: string) {
    const query = question.trim();
    if (!query || asking) return;
    setAsking(true);
    setAns("");
    setInteractionId(null);
    abort.current = new AbortController();
    api.ask(query, {
      signal: abort.current.signal,
      onToken: (tok) => setAns((a) => a + tok),
      onDone: (id) => {
        setAsking(false);
        setInteractionId(id);
        abort.current = null;
      },
      onError: () => {
        setAns("Sorry — the assistant is unavailable right now. Please try again.");
        setAsking(false);
        abort.current = null;
        say("Assistant unavailable.");
      },
    });
  }
  function stop() {
    abort.current?.abort();
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
      <p className="demo-note">Answers come from today's real tasks — never guesses.</p>
      <div className="chips">
        {PROMPTS.map((p) => (
          <button key={p} className="chip" disabled={asking} onClick={() => { setQ(p); ask(p); }}>
            {p}
          </button>
        ))}
      </div>
      <div className="ask-row" style={{ marginTop: 10 }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder='e.g. "What is still pending?"'
          aria-label="Ask about today"
          onKeyDown={(e) => e.key === "Enter" && ask(q)}
        />
        {asking ? (
          <button className="ask-go" onClick={stop}>
            Stop
          </button>
        ) : (
          <button className="ask-go" onClick={() => ask(q)}>
            Ask
          </button>
        )}
      </div>
      {(ans || asking) && (
        <div>
          <p className="answer" aria-live="polite">
            {ans || "Thinking…"}
          </p>
          {interactionId !== null && <p className="demo-note">Logged for review · #{interactionId}</p>}
        </div>
      )}
    </section>
  );
}

/* ================= Task sheet (add + edit) ================= */

function TaskSheet({
  editing,
  members,
  close,
  reload,
  say,
}: {
  editing?: Task;
  members: Member[];
  close: () => void;
  reload: () => void;
  say: (m: string) => void;
}) {
  const [title, setTitle] = useState(editing?.title ?? "");
  const [description, setDescription] = useState(editing?.description ?? "");
  const [type, setType] = useState(editing?.task_type ?? "medication");
  const [priority, setPriority] = useState(editing?.priority ?? "normal");
  const [assigned, setAssigned] = useState<string>(String(editing?.assigned_member_id ?? ""));
  const [due, setDue] = useState(() =>
    editing
      ? toLocalInput(new Date(editing.due_at))
      : toLocalInput(new Date(Date.now() + 3600e3))
  );
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function save() {
    if (!title.trim()) {
      setErr("Please enter a title — e.g. Evening BP tablet.");
      return;
    }
    if (!due) {
      setErr("Please pick a date and time.");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const recips = await api.recipients();
      if (!recips[0]) {
        await api.seed();
      }
      const list = await api.recipients();
      const payload = {
        title: title.trim(),
        description: description.trim(),
        task_type: type,
        priority,
        due_at: new Date(due).toISOString(),
        care_recipient_id: list[0].id,
        assigned_member_id: assigned ? Number(assigned) : null,
      };
      if (editing) {
        await api.updateTask(editing.id, { ...payload, version: editing.version });
        say("Task updated.");
      } else {
        await api.addTask(payload);
        say("Task added to today.");
      }
      await reload();
      close();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save — try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="sheet-bg" onClick={close}>
      <div className="sheet" role="dialog" aria-label={editing ? "Edit task" : "Add task"} onClick={(e) => e.stopPropagation()}>
        <div className="grip" />
        <div className="sheet-head">
          <span className="prog-label" style={{ fontSize: 19 }}>
            <span className="ic">
              <Icon name={editing ? "pencil" : "plus"} size={19} />
            </span>{" "}
            {editing ? "Edit task" : "Add a task"}
          </span>
          <button className="icon-btn" onClick={close} aria-label="Close">
            <Icon name="x" size={20} />
          </button>
        </div>
        <label htmlFor="task-title">Title *</label>
        <input
          id="task-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Evening BP tablet"
        />
        <label htmlFor="task-desc">Description (optional)</label>
        <input
          id="task-desc"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="e.g. With dinner, 8 pm"
        />
        <div className="form-2">
          <div>
            <label htmlFor="task-type">Type</label>
            <select id="task-type" value={type} onChange={(e) => setType(e.target.value)}>
              {TYPES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="task-priority">Priority</label>
            <select id="task-priority" value={priority} onChange={(e) => setPriority(e.target.value)}>
              <option value="low">low</option>
              <option value="normal">normal</option>
              <option value="high">high</option>
            </select>
          </div>
        </div>
        <label htmlFor="task-due">Due date & time *</label>
        <input id="task-due" type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
        <label htmlFor="task-assigned">Assigned to (optional)</label>
        <select id="task-assigned" value={assigned} onChange={(e) => setAssigned(e.target.value)}>
          <option value="">Nobody yet</option>
          {members.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
        <button className="btn-primary" disabled={busy} onClick={save}>
          {busy ? "Saving…" : editing ? "Save changes" : "Add task"}
        </button>
        {err && <p className="err">{err}</p>}
      </div>
    </div>
  );
}
