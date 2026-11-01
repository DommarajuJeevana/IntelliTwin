
"use client";

import { useEffect, useMemo, useState } from "react";
import { useApi } from "@/lib/useApi";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function getCalendarDays(date) {
  const first = startOfMonth(date);
  const mondayOffset = (first.getDay() + 6) % 7;
  const start = new Date(first);
  start.setDate(first.getDate() - mondayOffset);

  return Array.from({ length: 42 }, (_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    return day;
  });
}

function dateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatMonth(date) {
  return date.toLocaleDateString([], {
    month: "long",
    year: "numeric",
  });
}

function formatSelectedDate(date) {
  return date.toLocaleDateString([], {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function formatTime(value) {
  if (!value) return "";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";

  return date.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}

function isSameDay(first, second) {
  return dateKey(first) === dateKey(second);
}

function isToday(date) {
  return isSameDay(date, new Date());
}

function CalendarItem({ item }) {
  const isTask = item.type === "task";

  return (
    <div
      className={`truncate border-l-2 px-1.5 py-1 text-[11px] ${
        isTask
          ? "border-amber-400/70 bg-amber-400/[0.07] text-amber-300"
          : "border-accent/70 bg-accent/[0.07] text-accent"
      }`}
      title={`${formatTime(item.date)}${item.endDate ? ` – ${formatTime(item.endDate)}` : ""} ${item.title}`}
    >
      <span className="mr-1 opacity-60">
        {formatTime(item.date)}
        {item.endDate ? `–${formatTime(item.endDate)}` : ""}
      </span>
      {item.title}
    </div>
  );
}

function toLocalDateTime(date, time) {
  const [hours, minutes] = time.split(":").map(Number);
  const result = new Date(date);
  result.setHours(hours, minutes, 0, 0);
  return result;
}

const inputClass =
  "h-11 w-full min-w-0 border border-ink-700 bg-ink-950/70 px-3 text-sm text-text outline-none focus:border-accent";

export default function CalendarPage() {
  const { get, post } = useApi();

  const [currentMonth, setCurrentMonth] = useState(() =>
    startOfMonth(new Date())
  );
  const [selectedDate, setSelectedDate] = useState(() => new Date());

  const [tasks, setTasks] = useState([]);
  const [events, setEvents] = useState([]);

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const [itemType, setItemType] = useState("event");
  const [title, setTitle] = useState("");
  const [fromTime, setFromTime] = useState("10:00");
  const [toTime, setToTime] = useState("11:00");
  const [priority, setPriority] = useState("medium");
  const [location, setLocation] = useState("");

  const calendarDays = useMemo(
    () => getCalendarDays(currentMonth),
    [currentMonth]
  );

  useEffect(() => {
    let active = true;

    async function loadCalendarData() {
      try {
        setLoading(true);
        setError("");

        const [taskResponse, calendarResponse] = await Promise.all([
          get("/tasks"),
          get("/calendar"),
        ]);

        const taskItems = Array.isArray(taskResponse)
          ? taskResponse
          : taskResponse?.items ??
            taskResponse?.tasks ??
            taskResponse?.data ??
            [];

        const calendarItems = Array.isArray(calendarResponse)
          ? calendarResponse
          : calendarResponse?.items ??
            calendarResponse?.events ??
            calendarResponse?.calendar ??
            calendarResponse?.data ??
            [];

        if (active) {
          setTasks(taskItems);
          setEvents(calendarItems);
        }
      } catch (err) {
        if (active) {
          setError(err?.message || "Unable to load calendar.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    loadCalendarData();

    return () => {
      active = false;
    };
  }, [get]);

  const calendarItems = useMemo(() => {
    const taskItems = tasks
      .filter((task) => task.scheduledStart)
      .map((task) => ({
        ...task,
        type: "task",
        date: task.scheduledStart,
        endDate: task.scheduledEnd || null,
      }));

    const eventItems = events
      .filter((event) => event.startsAt)
      .map((event) => ({
        ...event,
        type: "event",
        date: event.startsAt,
        endDate: event.endsAt || null,
      }));

    return [...taskItems, ...eventItems];
  }, [tasks, events]);

  function itemsForDay(day) {
    return calendarItems
      .filter((item) => {
        const itemDate = new Date(item.date);
        return (
          !Number.isNaN(itemDate.getTime()) &&
          isSameDay(itemDate, day)
        );
      })
      .sort(
        (a, b) =>
          new Date(a.date).getTime() - new Date(b.date).getTime()
      );
  }

  const selectedItems = useMemo(
    () => itemsForDay(selectedDate),
    [calendarItems, selectedDate]
  );

  function goToPreviousMonth() {
    setCurrentMonth(
      new Date(
        currentMonth.getFullYear(),
        currentMonth.getMonth() - 1,
        1
      )
    );
  }

  function goToNextMonth() {
    setCurrentMonth(
      new Date(
        currentMonth.getFullYear(),
        currentMonth.getMonth() + 1,
        1
      )
    );
  }

  function goToToday() {
    const now = new Date();
    setCurrentMonth(startOfMonth(now));
    setSelectedDate(now);
  }

  function selectDay(day) {
    setSelectedDate(day);

    if (
      day.getMonth() !== currentMonth.getMonth() ||
      day.getFullYear() !== currentMonth.getFullYear()
    ) {
      setCurrentMonth(startOfMonth(day));
    }
  }

  const validTimeRange =
    Boolean(fromTime) &&
    Boolean(toTime) &&
    toTime > fromTime;

  async function addItem(event) {
    event.preventDefault();

    const cleanTitle = title.trim();

    if (!cleanTitle || busy) return;

    if (!validTimeRange) {
      setError("The To time must be later than the From time.");
      return;
    }

    try {
      setBusy(true);
      setError("");

      const startDate = toLocalDateTime(selectedDate, fromTime);
      const endDate = toLocalDateTime(selectedDate, toTime);

      if (
        Number.isNaN(startDate.getTime()) ||
        Number.isNaN(endDate.getTime()) ||
        endDate <= startDate
      ) {
        throw new Error("Please enter a valid start and end time.");
      }

      const startsAt = startDate.toISOString();
      const endsAt = endDate.toISOString();

      if (itemType === "event") {
        const response = await post("/calendar", {
          title: cleanTitle,
          startsAt,
          endsAt,
          location: location.trim() || undefined,
        });

        const created =
          response?.item ?? response?.event ?? response?.data;

        if (created && typeof created === "object") {
          setEvents((current) => [...current, created]);
        } else {
          const refreshed = await get("/calendar");
          setEvents(
            Array.isArray(refreshed)
              ? refreshed
              : refreshed?.items ?? refreshed?.events ?? []
          );
        }
      } else {
        const response = await post("/tasks", {
          title: cleanTitle,
          priority,
          scheduledStart: startsAt,
          scheduledEnd: endsAt,
        });

        const created =
          response?.item ?? response?.task ?? response?.data;

        if (created && typeof created === "object") {
          setTasks((current) => [...current, created]);
        } else {
          const refreshed = await get("/tasks");
          setTasks(
            Array.isArray(refreshed)
              ? refreshed
              : refreshed?.items ?? refreshed?.tasks ?? []
          );
        }

        // The backend task scheduler creates and links
        // the corresponding calendar event.
      }

      setTitle("");
      setLocation("");
      setPriority("medium");
    } catch (err) {
      setError(err?.message || "Unable to add calendar item.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="w-full">
      <div className="mx-auto max-w-[1400px]">
        <header className="mb-6">
          <div className="flex items-center gap-3">
            <div className="h-2 w-2 rounded-full bg-accent" />
            <span className="text-[11px] font-medium uppercase tracking-[0.2em] text-accent/80">
              Time workspace
            </span>
          </div>

          <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-text sm:text-3xl">
            Calendar
          </h1>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-text-dim">
            View scheduled events and tasks together. Select a day and set
            both the start and end times.
          </p>
        </header>

        {error && (
          <div
            role="alert"
            className="mb-5 border rounded-lg border-rose-400/20 bg-rose-400/[0.04] px-4 py-3 text-sm text-rose-300"
          >
            {error}
          </div>
        )}

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
          <section className="min-w-0 border rounded-xl border-ink-700 bg-ink-900/70">
            <div className="flex flex-col gap-4 border-b border-ink-700 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={goToPreviousMonth}
                  aria-label="Previous month"
                  className="flex h-9 w-9 items-center justify-center border border-ink-700 text-text-dim hover:bg-white/[0.04] hover:text-text"
                >
                  ‹
                </button>

                <button
                  type="button"
                  onClick={goToNextMonth}
                  aria-label="Next month"
                  className="flex h-9 w-9 items-center justify-center border border-ink-700 text-text-dim hover:bg-white/[0.04] hover:text-text"
                >
                  ›
                </button>

                <h2 className="ml-1 text-lg font-medium text-text">
                  {formatMonth(currentMonth)}
                </h2>
              </div>

              <button
                type="button"
                onClick={goToToday}
                className="h-9 border border-accent/20 px-4 text-xs font-medium text-accent hover:bg-accent/[0.06]"
              >
                Today
              </button>
            </div>

            <div className="flex gap-5 border-b border-ink-700 px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-accent" />
                <span className="text-xs text-text-dim">Events</span>
              </div>

              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-amber-400" />
                <span className="text-xs text-text-dim">Scheduled tasks</span>
              </div>
            </div>

            <div className="grid grid-cols-7 border-b border-ink-700">
              {WEEKDAYS.map((day) => (
                <div
                  key={day}
                  className="border-r border-ink-700 px-1 py-3 text-center text-[10px] font-medium uppercase tracking-wider text-text-dim/70 last:border-r-0 sm:px-2 sm:text-[11px]"
                >
                  {day}
                </div>
              ))}
            </div>

            <div className="grid grid-cols-7">
              {calendarDays.map((day) => {
                const dayItems = itemsForDay(day);
                const outsideMonth =
                  day.getMonth() !== currentMonth.getMonth();
                const selected = isSameDay(day, selectedDate);
                const todayDay = isToday(day);

                return (
                  <button
                    key={dateKey(day)}
                    type="button"
                    onClick={() => selectDay(day)}
                    aria-pressed={selected}
                    aria-label={`${formatSelectedDate(day)}, ${dayItems.length} scheduled items`}
                    className={`min-h-[100px] min-w-0 overflow-hidden border-b border-r border-ink-700 p-1.5 text-left align-top transition-colors hover:bg-white/[0.025] sm:min-h-[120px] sm:p-2 ${
                      outsideMonth ? "bg-ink-950 opacity-45" : ""
                    } ${
                      selected
                        ? "bg-accent/[0.035] ring-1 ring-inset ring-accent/25"
                        : ""
                    }`}
                  >
                    <div className="mb-2 flex items-center justify-between">
                      <span
                        className={`flex h-6 w-6 items-center justify-center text-xs sm:h-7 sm:w-7 ${
                          todayDay
                            ? "bg-accent font-semibold text-ink-950"
                            : selected
                              ? "text-accent"
                              : "text-text-dim"
                        }`}
                      >
                        {day.getDate()}
                      </span>

                      {dayItems.length > 0 && (
                        <span className="text-[10px] text-text-dim/70">
                          {dayItems.length}
                        </span>
                      )}
                    </div>

                    <div className="space-y-1">
                      {dayItems.slice(0, 3).map((item) => (
                        <CalendarItem
                          key={`${item.type}-${item._id ?? item.id ?? item.title}`}
                          item={item}
                        />
                      ))}

                      {dayItems.length > 3 && (
                        <p className="px-1 text-[10px] text-text-dim/70">
                          +{dayItems.length - 3} more
                        </p>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          <aside className="space-y-5">
            <section className="border rounded-xl border-ink-700 bg-ink-900/70">
              <div className="border-b border-ink-700 px-5 py-4">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-accent/70">
                  Selected day
                </p>

                <h2 className="mt-2 text-base font-medium text-text">
                  {formatSelectedDate(selectedDate)}
                </h2>
              </div>

              {loading ? (
                <div className="px-5 py-8 text-sm text-text-dim/70">
                  Loading calendar...
                </div>
              ) : selectedItems.length === 0 ? (
                <div className="px-5 py-8">
                  <p className="text-sm text-text-dim">Nothing scheduled.</p>
                  <p className="mt-1 text-xs leading-5 text-text-dim/70">
                    Add a task or event for this day below.
                  </p>
                </div>
              ) : (
                <div>
                  {selectedItems.map((item) => (
                    <div
                      key={`${item.type}-${item._id ?? item.id ?? item.title}`}
                      className="border-b border-ink-700 px-5 py-4 last:border-b-0"
                    >
                      <div className="flex items-start gap-3">
                        <span
                          className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                            item.type === "task"
                              ? "bg-amber-400"
                              : "bg-accent"
                          }`}
                        />

                        <div className="min-w-0">
                          <p className="text-sm text-text">{item.title}</p>

                          <p className="mt-1 text-xs text-text-dim">
                            {formatTime(item.date)}
                            {item.endDate
                              ? ` – ${formatTime(item.endDate)}`
                              : ""}
                            {" · "}
                            {item.type === "task"
                              ? "Scheduled task"
                              : "Event"}
                          </p>

                          {item.location && (
                            <p className="mt-1 text-xs text-text-dim/70">
                              {item.location}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="border rounded-xl border-ink-700 bg-ink-900/70">
              <div className="border-b border-ink-700 px-5 py-4">
                <p className="text-sm font-medium text-text">
                  Add to calendar
                </p>
                <p className="mt-1 text-xs leading-5 text-text-dim">
                  {formatSelectedDate(selectedDate)}
                </p>
              </div>

              <form onSubmit={addItem} className="space-y-4 p-5">
                <div className="grid grid-cols-2 border border-ink-700">
                  <button
                    type="button"
                    onClick={() => setItemType("event")}
                    className={`h-9 text-xs transition-colors ${
                      itemType === "event"
                        ? "bg-accent/10 text-accent"
                        : "text-text-dim/70 hover:text-text-dim"
                    }`}
                  >
                    Event
                  </button>

                  <button
                    type="button"
                    onClick={() => setItemType("task")}
                    className={`h-9 text-xs transition-colors ${
                      itemType === "task"
                        ? "bg-amber-400/10 text-amber-300"
                        : "text-text-dim/70 hover:text-text-dim"
                    }`}
                  >
                    Task
                  </button>
                </div>

                <div>
                  <label
                    htmlFor="calendar-title"
                    className="mb-2 block text-xs text-text-dim"
                  >
                    Title
                  </label>
                  <input
                    id="calendar-title"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder={itemType === "task" ? "Task title" : "Event title"}
                    required
                    className={inputClass}
                  />
                </div>

                <div>
                  <p className="mb-2 text-xs text-text-dim">Time</p>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="min-w-0">
                      <label
                        htmlFor="calendar-from-time"
                        className="mb-2 block text-xs text-text-dim"
                      >
                        From
                      </label>
                      <input
                        id="calendar-from-time"
                        type="time"
                        value={fromTime}
                        onChange={(event) => setFromTime(event.target.value)}
                        required
                        className={inputClass}
                      />
                    </div>

                    <div className="min-w-0">
                      <label
                        htmlFor="calendar-to-time"
                        className="mb-2 block text-xs text-text-dim"
                      >
                        To
                      </label>
                      <input
                        id="calendar-to-time"
                        type="time"
                        value={toTime}
                        min={fromTime || undefined}
                        onChange={(event) => setToTime(event.target.value)}
                        required
                        className={inputClass}
                      />
                    </div>
                  </div>

                  {!validTimeRange && (
                    <p className="mt-2 text-xs text-amber-300">
                      End time must be later than start time.
                    </p>
                  )}
                </div>

                {itemType === "task" ? (
                  <div>
                    <label
                      htmlFor="calendar-priority"
                      className="mb-2 block text-xs text-text-dim"
                    >
                      Priority
                    </label>
                    <select
                      id="calendar-priority"
                      value={priority}
                      onChange={(event) => setPriority(event.target.value)}
                      className={inputClass}
                    >
                      <option value="high">High priority</option>
                      <option value="medium">Medium priority</option>
                      <option value="low">Low priority</option>
                    </select>
                  </div>
                ) : (
                  <div>
                    <label
                      htmlFor="calendar-location"
                      className="mb-2 block text-xs text-text-dim"
                    >
                      Location (optional)
                    </label>
                    <input
                      id="calendar-location"
                      value={location}
                      onChange={(event) => setLocation(event.target.value)}
                      placeholder="Location"
                      className={inputClass}
                    />
                  </div>
                )}

                <button
                  type="submit"
                  disabled={busy || !title.trim() || !validTimeRange}
                  className={`h-11 w-full text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                    itemType === "task"
                      ? "border rounded-lg border-amber-400/25 bg-amber-400/10 text-amber-300 hover:bg-amber-400/15"
                      : "border border-accent/25 bg-accent/10 text-accent hover:bg-accent/15"
                  }`}
                >
                  {busy ? "Adding..." : `Add ${itemType}`}
                </button>
              </form>
            </section>

            <section className="border-l border-accent/30 pl-4">
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-accent/70">
                Compass connection
              </p>
              <p className="mt-2 text-sm leading-6 text-text-dim">
                Give each task or commitment a defined time window to make
                your schedule easier to follow.
              </p>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}
