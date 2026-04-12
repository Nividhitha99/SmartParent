"use client";

import { useEffect, useState } from "react";
import { addTaskFromNote, getTasks, toggleTaskDone, deleteTask } from "@/lib/tasksApi";
import type { Task } from "@/types/plan";

const TYPE_LABELS: Record<Task["type"], string> = {
  homework: "Homework",
  project: "Project",
  event: "Event",
  supply: "Supplies",
};

const TYPE_COLOURS: Record<Task["type"], string> = {
  homework: "bg-blue-50 text-blue-700",
  project: "bg-purple-50 text-purple-700",
  event: "bg-amber-50 text-amber-700",
  supply: "bg-green-50 text-green-700",
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [noteInput, setNoteInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load tasks on mount
  useEffect(() => {
    fetchTasks();
  }, []);

  async function fetchTasks() {
    setLoading(true);
    try {
      setTasks(await getTasks());
    } catch (e: any) {
      setError(e?.message || "Failed to load tasks");
    } finally {
      setLoading(false);
    }
  }

  async function handleAdd() {
    if (!noteInput.trim()) return;
    setAdding(true);
    setError(null);
    try {
      const task = await addTaskFromNote(noteInput.trim());
      setTasks((prev) => [task, ...prev]);
      setNoteInput("");
    } catch (e: any) {
      setError(e?.message || "Failed to add task");
    } finally {
      setAdding(false);
    }
  }

  async function handleToggle(taskId: string) {
    try {
      const updated = await toggleTaskDone(taskId);
      setTasks((prev) => prev.map((t) => (t.task_id === taskId ? updated : t)));
    } catch (e: any) {
      setError(e?.message || "Failed to update task");
    }
  }

  async function handleDelete(taskId: string) {
    try {
      await deleteTask(taskId);
      setTasks((prev) => prev.filter((t) => t.task_id !== taskId));
    } catch (e: any) {
      setError(e?.message || "Failed to delete task");
    }
  }

  const pending = tasks.filter((t) => !t.done);
  const done = tasks.filter((t) => t.done);

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-3xl px-4 py-8">
        <header className="mb-6">
          <h1 className="text-3xl font-semibold">Homework & Tasks</h1>
          <p className="mt-1 text-gray-600">
            Paste a school note or homework reminder to create a tracked task.
          </p>
        </header>

        {/* Add task card */}
        <section className="rounded-2xl border bg-white p-5 shadow-sm">
          <p className="mb-2 text-sm font-medium text-gray-700">New task from note</p>
          <div className="flex gap-2">
            <textarea
              value={noteInput}
              onChange={(e) => setNoteInput(e.target.value)}
              placeholder="e.g. Science project due 4/15 — bring scissors, glue, chart paper"
              className="h-24 w-full resize-none rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleAdd}
              disabled={adding || !noteInput.trim()}
              className="h-24 shrink-0 rounded-xl bg-blue-600 px-5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
            >
              {adding ? "Adding…" : "Add"}
            </button>
          </div>
        </section>

        {/* Error */}
        {error && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="mt-6 animate-pulse space-y-3">
            <div className="h-24 rounded-2xl bg-gray-200" />
            <div className="h-24 rounded-2xl bg-gray-200" />
          </div>
        )}

        {/* Task board */}
        {!loading && (
          <div className="mt-6 space-y-8">
            {/* Pending */}
            <TaskSection
              title="Pending"
              count={pending.length}
              tasks={pending}
              onToggle={handleToggle}
              onDelete={handleDelete}
            />

            {/* Done */}
            {done.length > 0 && (
              <TaskSection
                title="Done"
                count={done.length}
                tasks={done}
                onToggle={handleToggle}
                onDelete={handleDelete}
                muted
              />
            )}

            {tasks.length === 0 && !loading && (
              <p className="text-sm text-gray-400">No tasks yet. Add one above.</p>
            )}
          </div>
        )}
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Task section (Pending / Done)
// ---------------------------------------------------------------------------

function TaskSection({
  title,
  count,
  tasks,
  onToggle,
  onDelete,
  muted = false,
}: {
  title: string;
  count: number;
  tasks: Task[];
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
  muted?: boolean;
}) {
  if (tasks.length === 0) return null;

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <h2 className={`text-base font-semibold ${muted ? "text-gray-400" : "text-gray-800"}`}>
          {title}
        </h2>
        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
          {count}
        </span>
      </div>
      <ul className="space-y-3">
        {tasks.map((task) => (
          <TaskCard
            key={task.task_id}
            task={task}
            onToggle={onToggle}
            onDelete={onDelete}
          />
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Individual task card
// ---------------------------------------------------------------------------

function TaskCard({
  task,
  onToggle,
  onDelete,
}: {
  task: Task;
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <li className={`rounded-2xl border bg-white p-4 shadow-sm ${task.done ? "opacity-60" : ""}`}>
      <div className="flex items-start gap-3">
        {/* Checkbox */}
        <input
          type="checkbox"
          checked={task.done}
          onChange={() => onToggle(task.task_id)}
          className="mt-1 h-4 w-4 shrink-0 rounded accent-blue-600"
        />

        {/* Body */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`text-base font-semibold ${
                task.done ? "text-gray-400 line-through" : "text-gray-900"
              }`}
            >
              {task.title}
            </span>

            {/* Type badge */}
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                TYPE_COLOURS[task.type]
              }`}
            >
              {TYPE_LABELS[task.type]}
            </span>

            {/* Project name badge */}
            {task.project_name && (
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                {task.project_name}
              </span>
            )}
          </div>

          {/* Deadline */}
          {(task.deadline_date || task.deadline_time) && (
            <p className="mt-1 text-xs text-gray-500">
              Due:{" "}
              <span className="font-medium text-gray-700">
                {[task.deadline_date, task.deadline_time].filter(Boolean).join(" at ")}
              </span>
            </p>
          )}

          {/* Supplies */}
          {task.supplies.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {task.supplies.map((s, i) => (
                <li
                  key={i}
                  className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-700"
                >
                  {s}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Delete */}
        <button
          onClick={() => onDelete(task.task_id)}
          className="shrink-0 rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-500"
          title="Delete task"
        >
          ✕
        </button>
      </div>
    </li>
  );
}
