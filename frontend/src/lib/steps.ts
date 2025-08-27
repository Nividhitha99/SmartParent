import type { PlanStep } from "@/types/plan";

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];

export function groupByDay(steps: PlanStep[]) {
  const map: Record<string, PlanStep[]> = {};
  for (const d of WEEKDAYS) map[d] = [];
  for (const s of steps) {
    if (s.when && WEEKDAYS.includes(s.when)) {
      map[s.when].push(s);
    }
  }
  return map;
}

export function getWeekDates(startDate: Date) {
  const dates: Record<string, string> = {};
  WEEKDAYS.forEach((d, idx) => {
    const dt = new Date(startDate);
    dt.setDate(startDate.getDate() + idx);
    dates[d] = dt.toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  });
  return dates;
}
