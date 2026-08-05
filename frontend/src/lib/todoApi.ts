import type { PlanResponse } from "@/types/plan";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL!;

export async function getTodo(): Promise<PlanResponse[]> {
  const res = await fetch(`${BASE}/todo`);
  if (!res.ok) throw new Error(`Failed to fetch to-do list: ${res.status}`);
  return res.json();
}

export async function toggleTodoDone(planId: string): Promise<PlanResponse> {
  const res = await fetch(`${BASE}/todo/${planId}/done`, { method: "PATCH" });
  if (!res.ok) throw new Error(`Failed to update: ${res.status}`);
  return res.json();
}

export async function deleteTodo(planId: string): Promise<void> {
  const res = await fetch(`${BASE}/todo/${planId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete: ${res.status}`);
}
