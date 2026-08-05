"use client";

import { useEffect, useState } from "react";
import { getTodo, toggleTodoDone, deleteTodo } from "@/lib/todoApi";
import type { PlanResponse } from "@/types/plan";

const ACTIVITY_TYPE_LABELS: Record<string, string> = {
  assignment: "Assignment",
  project: "Project",
  prep: "Test/Competition Prep",
};

const ACTIVITY_TYPE_COLOURS: Record<string, string> = {
  assignment: "bg-blue-50 text-blue-700",
  project: "bg-purple-50 text-purple-700",
  prep: "bg-amber-50 text-amber-700",
};

export default function TodoPage() {
  const [items, setItems] = useState<PlanResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTodo();
  }, []);

  async function fetchTodo() {
    setLoading(true);
    try {
      setItems(await getTodo());
    } catch (e: any) {
      setError(e?.message || "Failed to load to-do list");
    } finally {
      setLoading(false);
    }
  }

  async function handleToggle(planId: string) {
    try {
      const updated = await toggleTodoDone(planId);
      setItems((prev) => prev.map((i) => (i.plan_id === planId ? updated : i)));
    } catch (e: any) {
      setError(e?.message || "Failed to update");
    }
  }

  async function handleDelete(planId: string) {
    try {
      await deleteTodo(planId);
      setItems((prev) => prev.filter((i) => i.plan_id !== planId));
    } catch (e: any) {
      setError(e?.message || "Failed to delete");
    }
  }

  const pending = items.filter((i) => !i.done);
  const done = items.filter((i) => i.done);

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-3xl px-4 py-8">
        <header className="mb-6">
          <h1 className="text-3xl font-semibold">To-Do List</h1>
          <p className="mt-1 text-gray-600">
            Every assignment, project, and exam/competition prep you've submitted on the
            Activity page, in order of due date.
          </p>
        </header>

        {error && (
          <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <div className="space-y-3">
            <div className="h-20 animate-pulse rounded-2xl bg-gray-200" />
            <div className="h-20 animate-pulse rounded-2xl bg-gray-200" />
          </div>
        ) : (
          <div className="space-y-8">
            <TodoSection title="Pending" count={pending.length} items={pending} onToggle={handleToggle} onDelete={handleDelete} />
            {done.length > 0 && (
              <TodoSection title="Done" count={done.length} items={done} onToggle={handleToggle} onDelete={handleDelete} muted />
            )}
            {items.length === 0 && (
              <p className="text-sm text-gray-400">
                Nothing yet — submit a homework, project, or exam/competition note on the
                Activity page and it'll show up here.
              </p>
            )}
          </div>
        )}
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Section (Pending / Done)
// ---------------------------------------------------------------------------

function TodoSection({
  title,
  count,
  items,
  onToggle,
  onDelete,
  muted = false,
}: {
  title: string;
  count: number;
  items: PlanResponse[];
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
  muted?: boolean;
}) {
  if (items.length === 0) return null;

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <h2 className={`text-base font-semibold ${muted ? "text-gray-400" : "text-gray-800"}`}>
          {title}
        </h2>
        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">{count}</span>
      </div>
      <ul className="space-y-3">
        {items.map((item) => (
          <TodoCard key={item.plan_id} item={item} onToggle={onToggle} onDelete={onDelete} />
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Individual to-do card
// ---------------------------------------------------------------------------

function TodoCard({
  item,
  onToggle,
  onDelete,
}: {
  item: PlanResponse;
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasDetails = item.materials.length > 0 || item.daily_plan.length > 0 || item.solutions.length > 0;

  return (
    <li className={`rounded-2xl border bg-white p-4 shadow-sm ${item.done ? "opacity-60" : ""}`}>
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={item.done}
          onChange={() => onToggle(item.plan_id)}
          className="mt-1 h-4 w-4 shrink-0 rounded accent-blue-600"
        />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => hasDetails && setExpanded((e) => !e)}
              className={`text-left text-base font-semibold ${
                item.done ? "text-gray-400 line-through" : "text-gray-900"
              } ${hasDetails ? "cursor-pointer hover:underline" : ""}`}
            >
              {item.title || "Activity"}
            </button>

            {item.activity_type && ACTIVITY_TYPE_LABELS[item.activity_type] && (
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${ACTIVITY_TYPE_COLOURS[item.activity_type]}`}>
                {ACTIVITY_TYPE_LABELS[item.activity_type]}
              </span>
            )}
          </div>

          {item.deadline_date && (
            <p className="mt-1 text-xs text-gray-500">
              Due: <span className="font-medium text-gray-700">{item.deadline_date}</span>
            </p>
          )}

          {expanded && hasDetails && (
            <div className="mt-3 space-y-3 border-t pt-3">
              {item.materials.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Materials</p>
                  <ul className="flex flex-wrap gap-1.5">
                    {item.materials.map((m) => (
                      <li key={m.name} className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-700">
                        {m.name}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {item.daily_plan.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Day-by-Day Plan</p>
                  <ol className="space-y-1.5">
                    {item.daily_plan.map((d, i) => (
                      <li key={i} className="text-sm text-gray-700">
                        <span className="font-medium text-gray-900">{d.day_label}:</span>{" "}
                        {d.tasks.join("; ")}
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {item.solutions.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Solutions</p>
                  <ol className="space-y-2">
                    {item.solutions.map((s, i) => (
                      <li key={i} className="text-sm text-gray-700">
                        <span className="font-medium text-gray-900">{i + 1}. {s.question}</span>
                        <p className="mt-0.5 whitespace-pre-line text-gray-600">{s.solution}</p>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          )}
        </div>

        <button
          onClick={() => onDelete(item.plan_id)}
          className="shrink-0 rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-500"
          title="Delete"
        >
          ✕
        </button>
      </div>
    </li>
  );
}
