export type PlanLink = { maps_url?: string; doordash_url?: string };
export type PlanStep = { type: string; title: string; items: string[]; when: string | null; links: PlanLink };
export type PlanResponse = { steps: PlanStep[]; raw_text: string };
