const MS_DAY = 86400000;

// The backend stores date-only due dates as midnight UTC. A value at exactly
// 00:00:00.000Z is therefore a calendar date, not a moment in time.
export function parseDue(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const dateOnly =
    date.getUTCHours() === 0 &&
    date.getUTCMinutes() === 0 &&
    date.getUTCSeconds() === 0 &&
    date.getUTCMilliseconds() === 0;
  return { date, dateOnly };
}

function dayNumber(date, utc) {
  const y = utc ? date.getUTCFullYear() : date.getFullYear();
  const m = utc ? date.getUTCMonth() : date.getMonth();
  const d = utc ? date.getUTCDate() : date.getDate();
  return Math.floor(Date.UTC(y, m, d) / MS_DAY);
}

export function daysFromToday(value) {
  const parsed = parseDue(value);
  if (!parsed) return null;
  return dayNumber(parsed.date, parsed.dateOnly) - dayNumber(new Date(), false);
}

/** { text, tone: "overdue" | "today" | "soon" | "later", days } or null. */
export function dueLabel(value) {
  const days = daysFromToday(value);
  if (days === null) return null;
  if (days < 0) return { text: `${-days}d overdue`, tone: "overdue", days };
  if (days === 0) return { text: "Today", tone: "today", days };
  if (days === 1) return { text: "Tomorrow", tone: "soon", days };
  if (days < 7) return { text: `In ${days} days`, tone: "soon", days };
  const parsed = parseDue(value);
  return {
    text: parsed.date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      ...(parsed.dateOnly ? { timeZone: "UTC" } : {}),
    }),
    tone: "later",
    days,
  };
}

export const DUE_TONE_CLASS = {
  overdue: "text-rose-300",
  today: "text-amber-300",
  soon: "text-text",
  later: "text-text-dim",
};

export function formatTime(value) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

export function relativeTime(value) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  const diff = Date.now() - d.getTime();
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function dayHeading(value) {
  const n = daysFromToday(value);
  const d = new Date(value);
  if (n === 0) return "Today";
  if (n === 1) return "Tomorrow";
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

export function greetingFor(hour) {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}
