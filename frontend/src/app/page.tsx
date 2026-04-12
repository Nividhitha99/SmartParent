"use client";

import { useState, useRef } from "react";
import { uploadMenuImage, planFromText } from "@/lib/api";
import type { PlanResponse, PlanStep, Recipe } from "@/types/plan";
import { WEEKDAYS, groupByDay, getWeekDates } from "@/lib/steps";

export default function HomePage() {
  const [steps, setSteps] = useState<PlanStep[] | null>(null);
  const [shoppingList, setShoppingList] = useState<string[]>([]);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [textInput, setTextInput] = useState("");

  function applyResponse(res: PlanResponse) {
    setSteps(res.steps);
    setShoppingList(res.shopping_list ?? []);
    setRecipes(res.recipes ?? []);
  }

  async function handleUpload(file: File) {
    setLoading(true);
    setError(null);
    setSteps(null);
    setShoppingList([]);
    setRecipes([]);
    try {
      applyResponse(await uploadMenuImage(file));
    } catch (e: any) {
      setError(e?.message || "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  async function handlePlanFromText() {
    if (!textInput.trim()) return;
    setLoading(true);
    setError(null);
    setSteps(null);
    setShoppingList([]);
    setRecipes([]);
    try {
      applyResponse(await planFromText(textInput.trim()));
    } catch (e: any) {
      setError(e?.message || "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-4xl px-4 py-8">
        <header className="mb-6">
          <h1 className="text-3xl font-semibold">SmartParent Planner</h1>
          <p className="text-gray-600 mt-1">
            Upload a school menu image or paste OCR text. We'll turn it into actionable steps.
          </p>
        </header>

        {/* Upload card */}
        <section className="rounded-2xl border bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-4 md:flex-row md:items-center">
            <div className="flex-1">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleUpload(f);
                }}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="inline-flex items-center rounded-xl border border-gray-300 bg-white px-4 py-2 text-sm font-medium hover:bg-gray-50"
                disabled={loading}
              >
                {loading ? "Processing…" : "Upload Menu Image"}
              </button>
              <p className="mt-2 text-xs text-gray-500">
                JPG/PNG. We'll detect days & meals automatically.
              </p>
            </div>

            <div className="flex-1">
              <div className="flex gap-2">
                <textarea
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  placeholder="Or paste OCR text / circular note here…"
                  className="h-24 w-full resize-none rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  onClick={handlePlanFromText}
                  className="h-24 shrink-0 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
                  disabled={loading || !textInput.trim()}
                  title="Create plan from text"
                >
                  Go
                </button>
              </div>
            </div>
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
            <div className="h-20 rounded-2xl bg-gray-200" />
            <div className="h-20 rounded-2xl bg-gray-200" />
            <div className="h-20 rounded-2xl bg-gray-200" />
          </div>
        )}

        {/* Results */}
        {steps && !loading && (
          <div className="mt-6 space-y-8">
            {/* Weekly plan */}
            <StepsByDay steps={steps} />

            {/* Shopping list */}
            {shoppingList.length > 0 && (
              <ShoppingListCard items={shoppingList} />
            )}

            {/* Recipes */}
            {recipes.length > 0 && (
              <RecipesAccordion recipes={recipes} />
            )}
          </div>
        )}

        {!steps && !loading && (
          <p className="mt-6 text-sm text-gray-500">
            Your steps will appear here after you upload or submit text.
          </p>
        )}
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Shopping List
// ---------------------------------------------------------------------------

function ShoppingListCard({ items }: { items: string[] }) {
  const [checked, setChecked] = useState<Set<string>>(() => new Set());

  function toggle(item: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      next.has(item) ? next.delete(item) : next.add(item);
      return next;
    });
  }

  const remaining = items.filter((i) => !checked.has(i)).length;

  return (
    <section className="rounded-2xl border bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Shopping List</h2>
        <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700">
          {remaining} / {items.length} remaining
        </span>
      </div>
      <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {items.map((item) => (
          <li key={item}>
            <label className="flex cursor-pointer items-center gap-3 rounded-xl p-2 hover:bg-gray-50">
              <input
                type="checkbox"
                checked={checked.has(item)}
                onChange={() => toggle(item)}
                className="h-4 w-4 rounded accent-blue-600"
              />
              <span
                className={`text-sm ${
                  checked.has(item) ? "text-gray-400 line-through" : "text-gray-800"
                }`}
              >
                {item}
              </span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Recipes Accordion
// ---------------------------------------------------------------------------

function RecipesAccordion({ recipes }: { recipes: Recipe[] }) {
  const [open, setOpen] = useState<string | null>(null);

  return (
    <section className="rounded-2xl border bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-lg font-semibold">Recipes</h2>
      <div className="divide-y">
        {recipes.map((r) => {
          const isOpen = open === r.food;
          return (
            <div key={r.food}>
              <button
                onClick={() => setOpen(isOpen ? null : r.food)}
                className="flex w-full items-center justify-between py-3 text-left"
              >
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-900">{r.food}</span>
                  {r.prep_time_mins > 0 && (
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
                      {r.prep_time_mins} min
                    </span>
                  )}
                </div>
                <span className="text-gray-400 text-sm">{isOpen ? "▲" : "▼"}</span>
              </button>

              {isOpen && (
                <div className="pb-4 pl-1 grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-500">
                      Ingredients
                    </p>
                    <ul className="space-y-1">
                      {r.ingredients.map((ing, idx) => (
                        <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
                          <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400" />
                          {ing}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-500">
                      Steps
                    </p>
                    <ol className="space-y-1.5">
                      {r.steps.map((step, idx) => (
                        <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
                          <span className="shrink-0 font-semibold text-blue-600">{idx + 1}.</span>
                          {step}
                        </li>
                      ))}
                    </ol>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Weekly plan (unchanged)
// ---------------------------------------------------------------------------

function StepsByDay({ steps }: { steps: PlanStep[] }) {
  const [weekStart, setWeekStart] = useState(() => {
    const d = new Date();
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    return new Date(d.setDate(diff));
  });

  const grouped = groupByDay(steps);
  const dates = getWeekDates(weekStart);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-600">Week starting:</label>
        <input
          type="date"
          value={weekStart.toISOString().substring(0, 10)}
          onChange={(e) => setWeekStart(new Date(e.target.value))}
          className="rounded-lg border px-2 py-1 text-sm"
        />
      </div>

      {WEEKDAYS.map((day) => (
        <div key={day} className="space-y-3">
          <h3 className="mb-2 text-lg font-semibold">
            {day}{" "}
            <span className="ml-2 text-sm text-gray-500">({dates[day]})</span>
          </h3>
          {grouped[day]?.length ? (
            <StepsList steps={grouped[day]} />
          ) : (
            <p className="text-sm text-gray-400">No tasks</p>
          )}
        </div>
      ))}
    </div>
  );
}

function StepsList({ steps }: { steps: PlanStep[] }) {
  return (
    <ol className="space-y-4">
      {steps.map((s, i) => (
        <li key={i} className="rounded-2xl border bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white">
                {i + 1}
              </div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="truncate text-base font-semibold">{s.title}</h3>
                  {s.when && (
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700">
                      {s.when}
                    </span>
                  )}
                  <span className="rounded-full bg-gray-50 px-2 py-0.5 text-[11px] uppercase tracking-wide text-gray-500">
                    {s.type}
                  </span>
                </div>
                {s.items?.length > 0 && (
                  <ul className="mt-2 flex flex-wrap gap-2">
                    {s.items.map((it, idx) => (
                      <li
                        key={idx}
                        className="rounded-full bg-gray-100 px-2.5 py-1 text-xs text-gray-700"
                      >
                        {it}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            <div className="flex shrink-0 gap-2">
              {s.links?.maps_url && (
                <a
                  href={s.links.maps_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium hover:bg-gray-50"
                >
                  Open in Maps
                </a>
              )}
              {s.links?.doordash_url && (
                <a
                  href={s.links.doordash_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium hover:bg-gray-50"
                >
                  DoorDash
                </a>
              )}
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}
