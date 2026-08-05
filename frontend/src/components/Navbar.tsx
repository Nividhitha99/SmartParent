"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { getReminders, dismissReminder } from "@/lib/remindersApi";
import type { Reminder } from "@/types/plan";

const NAV_LINKS = [
  { href: "/", label: "Activity" },
  { href: "/todo", label: "To-Do List" },
];

const POLL_INTERVAL_MS = 30_000;

// ---------------------------------------------------------------------------
// Bell SVG
// ---------------------------------------------------------------------------
function BellIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="h-5 w-5"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.8}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6 6 0 10-12 0v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Reminder dropdown panel
// ---------------------------------------------------------------------------
function ReminderDropdown({
  reminders,
  onDismiss,
}: {
  reminders: Reminder[];
  onDismiss: (id: string) => void;
}) {
  if (reminders.length === 0) {
    return (
      <div className="absolute right-0 top-full mt-2 w-80 rounded-2xl border bg-white p-4 shadow-lg">
        <p className="text-sm text-gray-500">No pending reminders.</p>
      </div>
    );
  }

  return (
    <div className="absolute right-0 top-full mt-2 w-80 rounded-2xl border bg-white shadow-lg overflow-hidden">
      <div className="border-b px-4 py-2.5">
        <p className="text-sm font-semibold text-gray-800">
          Reminders{" "}
          <span className="ml-1 rounded-full bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700">
            {reminders.length}
          </span>
        </p>
      </div>
      <ul className="max-h-72 divide-y overflow-y-auto">
        {reminders.map((r) => (
          <li key={r.reminder_id} className="flex items-start gap-3 px-4 py-3">
            {/* Dot */}
            <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-blue-500" />

            {/* Content */}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-gray-900">
                {r.event_name}
              </p>
              {(r.date || r.time) && (
                <p className="mt-0.5 text-xs text-gray-500">
                  {[r.date, r.time].filter(Boolean).join(" · ")}
                </p>
              )}
              <p className="mt-0.5 text-[10px] uppercase tracking-wide text-gray-400">
                via {r.source}
              </p>
            </div>

            {/* Dismiss */}
            <button
              onClick={() => onDismiss(r.reminder_id)}
              className="shrink-0 rounded-lg p-1 text-xs text-gray-400 hover:bg-red-50 hover:text-red-500"
              title="Dismiss"
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Navbar
// ---------------------------------------------------------------------------
export default function Navbar() {
  const pathname = usePathname();

  // Reminder state
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const bellRef = useRef<HTMLDivElement>(null);

  // Fetch reminders; silently ignore errors so a down backend doesn't break nav
  async function fetchReminders() {
    try {
      setReminders(await getReminders());
    } catch {
      // intentionally silent — backend may not be running yet
    }
  }

  // Initial fetch + polling every 30 s
  useEffect(() => {
    fetchReminders();
    const id = setInterval(fetchReminders, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    function handleOutsideClick(e: MouseEvent) {
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    if (dropdownOpen) {
      document.addEventListener("mousedown", handleOutsideClick);
    }
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, [dropdownOpen]);

  // Optimistic dismiss: remove from local state immediately, then call API
  async function handleDismiss(reminderId: string) {
    setReminders((prev) => prev.filter((r) => r.reminder_id !== reminderId));
    try {
      await dismissReminder(reminderId);
    } catch {
      // If API call fails, refetch to restore correct state
      fetchReminders();
    }
  }

  const pendingCount = reminders.length;

  return (
    <nav className="sticky top-0 z-40 border-b bg-white shadow-sm">
      <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
        {/* Logo */}
        <Link href="/" className="text-lg font-bold tracking-tight text-blue-600">
          SmartParent
        </Link>

        {/* Nav links */}
        <ul className="flex items-center gap-1">
          {NAV_LINKS.map(({ href, label }) => {
            const active = pathname === href;
            return (
              <li key={href}>
                <Link
                  href={href}
                  className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                    active
                      ? "bg-blue-50 text-blue-700"
                      : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                  }`}
                >
                  {label}
                </Link>
              </li>
            );
          })}
        </ul>

        {/* Bell with badge + dropdown */}
        <div ref={bellRef} className="relative">
          <button
            onClick={() => setDropdownOpen((prev) => !prev)}
            className="relative rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
            aria-label={`Reminders${pendingCount > 0 ? ` (${pendingCount} pending)` : ""}`}
          >
            <BellIcon />
            {pendingCount > 0 && (
              <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
                {pendingCount > 9 ? "9+" : pendingCount}
              </span>
            )}
          </button>

          {dropdownOpen && (
            <ReminderDropdown
              reminders={reminders}
              onDismiss={handleDismiss}
            />
          )}
        </div>
      </div>
    </nav>
  );
}
