import type { Reminder } from "@/types/plan";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL!;

export async function getReminders(): Promise<Reminder[]> {
  const res = await fetch(`${BASE}/reminders`);
  if (!res.ok) throw new Error(`Failed to fetch reminders: ${res.status}`);
  return res.json();
}

export async function dismissReminder(reminderId: string): Promise<void> {
  const res = await fetch(`${BASE}/reminders/${reminderId}/dismiss`, {
    method: "PATCH",
  });
  if (!res.ok) throw new Error(`Failed to dismiss reminder: ${res.status}`);
}
