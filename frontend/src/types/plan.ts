export type PlanLink = { maps_url?: string; doordash_url?: string };
export type PlanStep = { type: string; title: string; items: string[]; when: string | null; links: PlanLink };
export type Recipe = { food: string; ingredients: string[]; steps: string[]; prep_time_mins: number };

export type Material = { name: string; amazon_url: string; maps_url: string };
export type DailyPlanEntry = { date: string | null; day_label: string; tasks: string[] };
export type Solution = { question: string; solution: string };

export type PlanKind = "food" | "activity" | "other";
export type ActivityType = "assignment" | "project" | "prep" | null;

export type PlanResponse = {
  kind: PlanKind;
  steps: PlanStep[];
  raw_text: string;
  shopping_list: string[];
  recipes: Recipe[];
  activity_type: ActivityType;
  title: string | null;
  deadline_date: string | null;
  materials: Material[];
  daily_plan: DailyPlanEntry[];
  solutions: Solution[];
  plan_id: string;
  created_at: string;
  done: boolean;
};

export type Reminder = {
  reminder_id: string;
  event_name: string;
  date: string | null;
  time: string | null;
  source: "plan" | "task";
  dismissed: boolean;
  created_at: string;
};
