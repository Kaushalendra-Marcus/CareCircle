export interface Task {
  id: number;
  title: string;
  category: string;
  status: string;
  due_at: string;
  notes: string;
  recipient_id: number;
  completed_by_id: number | null;
  completed_by_name: string | null;
  completed_at: string | null;
  version: number;
}

export interface Today {
  date: string;
  overdue: Task[];
  due: Task[];
  done: Task[];
  counts: { overdue: number; due: number; done: number; total: number };
}

export interface Member {
  id: number;
  name: string;
  relation: string;
}

export interface Recipient {
  id: number;
  name: string;
  notes: string;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!r.ok) {
    const body = await r.text();
    throw new Error(body || `Request failed (${r.status})`);
  }
  return r.json() as Promise<T>;
}

export const api = {
  today: (recipientId?: number) =>
    req<Today>(
      `/api/tasks/today${recipientId ? `?recipient_id=${recipientId}` : ""}`
    ),
  recipients: () => req<Recipient[]>("/api/recipients"),
  members: () => req<Member[]>("/api/members"),
  addMember: (name: string) =>
    req<Member>("/api/members", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  addTask: (t: {
    title: string;
    category: string;
    due_at: string;
    notes?: string;
    recipient_id: number;
  }) => req<Task>("/api/tasks", { method: "POST", body: JSON.stringify(t) }),
  complete: (id: number, completed_by_id: number | null, version: number) =>
    req<Task>(`/api/tasks/${id}/complete`, {
      method: "POST",
      body: JSON.stringify({ completed_by_id, version }),
    }),
  reopen: (id: number) =>
    req<Task>(`/api/tasks/${id}/reopen`, { method: "POST", body: "{}" }),
  snooze: (id: number, version: number, hours = 2) =>
    req<Task>(`/api/tasks/${id}`, {
      method: "PATCH",
      body: JSON.stringify({
        due_at: new Date(Date.now() + hours * 3600e3).toISOString(),
        version,
      }),
    }),
  seed: () => req<{ seeded: boolean }>("/api/seed", { method: "POST" }),

  /** Stream the assistant answer. Calls onToken for each word, onDone at end. */
  ask: async (
    question: string,
    onToken: (t: string) => void,
    onDone: () => void,
    onError: (e: Error) => void
  ) => {
    try {
      const r = await fetch("/api/assistant/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (!r.ok || !r.body) throw new Error(`Assistant failed (${r.status})`);
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const p of parts) {
          for (const line of p.split("\n")) {
            if (line.startsWith("data:")) {
              const tok = line.slice(5).trim();
              if (tok && tok !== "[DONE]") onToken(tok + " ");
            } else if (line.startsWith("event: done")) {
              onDone();
            }
          }
        }
      }
      onDone();
    } catch (e) {
      onError(e instanceof Error ? e : new Error("stream failed"));
    }
  },
};

export function fmtTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}
