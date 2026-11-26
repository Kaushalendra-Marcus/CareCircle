const V1 = "/api/v1";

export interface Task {
  id: number;
  care_recipient_id: number;
  title: string;
  description: string;
  task_type: string;
  due_at: string;
  status: "pending" | "completed" | "cancelled";
  priority: string;
  assigned_member_id: number | null;
  assigned_member_name: string | null;
  completed_by_member_id: number | null;
  completed_by_name: string | null;
  completed_at: string | null;
  version: number;
}

export interface Today {
  date: string;
  recipient: { id: number; name: string } | null;
  summary: { total: number; completed: number; pending: number; overdue: number };
  overdue: Task[];
  due: Task[];
  done: Task[];
}

export interface Member {
  id: number;
  care_recipient_id: number | null;
  name: string;
  relationship: string;
  avatar_url: string | null;
}

export interface Recipient {
  id: number;
  name: string;
  date_of_birth: string | null;
  timezone: string;
  notes: string;
}

export interface Interaction {
  id: number;
  question: string;
  context_sent: string;
  answer: string;
  latency_ms: number;
  model_name: string;
  created_at: string;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (r.status === 204) return undefined as T;
  if (!r.ok) {
    const body = await r.text();
    throw new Error(body || `Request failed (${r.status})`);
  }
  return r.json() as Promise<T>;
}

export const api = {
  today: (recipientId?: number) =>
    req<Today>(`${V1}/today${recipientId ? `?care_recipient_id=${recipientId}` : ""}`),
  recipients: () => req<Recipient[]>(`${V1}/recipients`),
  members: () => req<Member[]>(`${V1}/family-members`),
  addMember: (name: string, care_recipient_id?: number) =>
    req<Member>(`${V1}/family-members`, {
      method: "POST",
      body: JSON.stringify({ name, care_recipient_id }),
    }),
  addTask: (t: {
    title: string;
    description?: string;
    task_type: string;
    due_at: string;
    priority?: string;
    care_recipient_id: number;
    assigned_member_id?: number | null;
  }) => req<Task>(`${V1}/tasks`, { method: "POST", body: JSON.stringify(t) }),
  updateTask: (id: number, patch: Record<string, unknown>) =>
    req<Task>(`${V1}/tasks/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  removeTask: (id: number) =>
    fetch(`${V1}/tasks/${id}`, { method: "DELETE" }).then((r) => {
      if (!r.ok && r.status !== 204) throw new Error(`Delete failed (${r.status})`);
    }),
  complete: (id: number, completed_by_member_id: number | null, version: number) =>
    req<Task>(`${V1}/tasks/${id}/complete`, {
      method: "POST",
      body: JSON.stringify({ completed_by_member_id, version }),
    }),
  reopen: (id: number) =>
    req<Task>(`${V1}/tasks/${id}/reopen`, { method: "POST", body: "{}" }),
  snooze: (id: number, version: number, hours = 2) =>
    req<Task>(`${V1}/tasks/${id}`, {
      method: "PATCH",
      body: JSON.stringify({
        due_at: new Date(Date.now() + hours * 3600e3).toISOString(),
        version,
      }),
    }),
  seed: () => req<{ seeded: boolean }>(`${V1}/seed`, { method: "POST" }),
  resetDemo: () => req<Record<string, unknown>>(`${V1}/seed/reset`, { method: "POST" }),

  /** Real SSE streaming: parses JSON {type:token|done|error} events. */
  ask: (
    question: string,
    opts: {
      onToken: (t: string) => void;
      onDone: (interactionId: number | null) => void;
      onError: (e: Error) => void;
      signal?: AbortSignal;
    }
  ) => {
    (async () => {
      try {
        const r = await fetch(`${V1}/assistant/ask`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question }),
          signal: opts.signal,
        });
        if (!r.ok || !r.body) throw new Error(`Assistant failed (${r.status})`);
        const reader = r.body.getReader();
        const dec = new TextDecoder();
        let buf = "";
        let doneId: number | null = null;
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });
          const parts = buf.split("\n\n");
          buf = parts.pop() ?? "";
          for (const p of parts) {
            for (const line of p.split("\n")) {
              if (!line.startsWith("data:")) continue;
              const evt = JSON.parse(line.slice(5).trim());
              if (evt.type === "token") opts.onToken(evt.content);
              else if (evt.type === "done") doneId = evt.interaction_id ?? null;
              else if (evt.type === "error") throw new Error(evt.message || "stream error");
            }
          }
        }
        opts.onDone(doneId);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") {
          opts.onDone(null);
          return;
        }
        opts.onError(e instanceof Error ? e : new Error("stream failed"));
      }
    })();
  },
};

export function fmtTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export function relTime(iso: string): string {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const h = Math.round(mins / 60);
  if (h < 24) return `${h}h ago`;
  return new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" });
}
