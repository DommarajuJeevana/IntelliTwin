import Link from "next/link";
import { Calendar, MapPin } from "lucide-react";
import Panel from "./Panel";
import { dayHeading, formatTime, daysFromToday } from "../../lib/format";

const WINDOW_DAYS = 7;
const MAX_EVENTS = 5;

export default function SchedulePanel({ calendar, onRetry, className = "" }) {
  const now = Date.now();
  const events = (calendar.data || [])
    .filter((e) => {
      if (!e.startsAt) return false;
      const days = daysFromToday(e.startsAt);
      const end = new Date(e.endsAt || e.startsAt).getTime();
      return days !== null && days <= WINDOW_DAYS && end >= now;
    })
    .sort((a, b) => new Date(a.startsAt) - new Date(b.startsAt))
    .slice(0, MAX_EVENTS);

  const groups = [];
  for (const event of events) {
    const heading = dayHeading(event.startsAt);
    const last = groups[groups.length - 1];
    if (last && last.heading === heading) last.events.push(event);
    else groups.push({ heading, events: [event] });
  }

  return (
    <Panel
      title="Schedule"
      icon={Calendar}
      href="/calendar"
      state={calendar}
      onRetry={onRetry}
      isEmpty={events.length === 0}
      emptyTitle="Nothing scheduled this week"
      emptyHint="Events for the next 7 days will appear here."
      emptyHref="/calendar"
      emptyLabel="Open calendar"
      className={className}
    >
      <div className="space-y-4">
        {groups.map((group) => (
          <div key={group.heading}>
            <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-text-dim/70">{group.heading}</p>
            <ul className="space-y-1">
              {group.events.map((event) => (
                <li key={event._id}>
                  <Link
                    href="/calendar"
                    className="flex gap-3 rounded-lg px-2 py-1.5 transition-colors hover:bg-white/[0.04]"
                  >
                    <span className="w-[4.5rem] shrink-0 pt-0.5 text-xs tabular-nums text-text-dim">
                      {formatTime(event.startsAt)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm text-text">{event.title}</span>
                      {event.location ? (
                        <span className="mt-0.5 flex items-center gap-1 truncate text-[11px] text-text-dim">
                          <MapPin aria-hidden="true" className="h-3 w-3 shrink-0" />
                          {event.location}
                        </span>
                      ) : null}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Panel>
  );
}
