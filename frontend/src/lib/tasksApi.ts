import type { Task } from "@/types/plan";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL!;

export async function addTaskFromNote(note: string): Promise<Task> {
  const res = await fetch(`${BASE}/tasks/from-note`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note }),
  });
  if (!res.ok) throw new Error(`Failed to create task: ${res.status}`);
  return res.json();
}

export async function getTasks(): Promise<Task[]> {
  const res = await fetch(`${BASE}/tasks`);
  if (!res.ok) throw new Error(`Failed to fetch tasks: ${res.status}`);
  return res.json();
}

export async function toggleTaskDone(taskId: string): Promise<Task> {
  const res = await fetch(`${BASE}/tasks/${taskId}/done`, { method: "PATCH" });
  if (!res.ok) throw new Error(`Failed to update task: ${res.status}`);
  return res.json();
}

export async function deleteTask(taskId: string): Promise<void> {
  const res = await fetch(`${BASE}/tasks/${taskId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete task: ${res.status}`);
}
