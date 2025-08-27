import type { PlanResponse } from "@/types/plan";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL!;

export async function uploadMenuImage(file: File): Promise<PlanResponse> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${BASE}/plan-to-upload`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

export async function planFromText(text: string): Promise<PlanResponse> {
  const fd = new FormData();
  fd.append("text", text);
  const res = await fetch(`${BASE}/plan-from-text`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`plan-from-text failed: ${res.status}`);
  return res.json();
}
