export type PlanLink = { maps_url?: string; doordash_url?: string };
export type PlanStep = { type: string; title: string; items: string[]; when: string | null; links: PlanLink };
export type Recipe = { food: string; ingredients: string[]; steps: string[]; prep_time_mins: number };
export type PlanResponse = { steps: PlanStep[]; raw_text: string; shopping_list: string[]; recipes: Recipe[] };

export type Reminder = {
  reminder_id: string;
  event_name: string;
  date: string | null;
  time: string | null;
  source: "plan" | "task";
  dismissed: boolean;
  created_at: string;
};

export type Task = {
  task_id: string;
  title: string;
  project_name: string | null;
  type: "homework" | "project" | "event" | "supply";
  deadline_date: string | null;
  deadline_time: string | null;
  supplies: string[];
  done: boolean;
  created_at: string;
};
