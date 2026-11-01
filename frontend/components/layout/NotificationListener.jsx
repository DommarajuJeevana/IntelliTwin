"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../context/AuthContext";
import { api } from "../../lib/api";

const POLL_INTERVAL = 10000;

export default function NotificationListener() {
  const { token } = useAuth();
  const router = useRouter();
  const knownNotifications = useRef(new Set());
  const [visibleNotifications, setVisibleNotifications] = useState([]);
  const [permission, setPermission] = useState("default");

  useEffect(() => {
    if (typeof window !== "undefined" && "Notification" in window) {
      setPermission(Notification.permission);
    }
  }, []);

  // Permission requests must be initiated by a user action, not a mount effect.
  const requestPermission = useCallback(async () => {
    if (typeof window === "undefined" || !("Notification" in window)) return;
    try {
      const nextPermission = await Notification.requestPermission();
      setPermission(nextPermission);
    } catch (error) {
      console.warn("[Notifications] Permission request failed:", error);
    }
  }, []);

  const checkNotifications = useCallback(async () => {
    if (!token) return;

    try {
      const data = await api.get("/notifications?include_read=false", token);
      const notifications = data.notifications || [];
      const freshNotifications = [];

      for (const notification of notifications) {
        const id = notification?._id;
        if (!id || knownNotifications.current.has(id)) continue;

        knownNotifications.current.add(id);
        freshNotifications.push(notification);

        if (
          typeof window !== "undefined" &&
          "Notification" in window &&
          Notification.permission === "granted"
        ) {
          try {
            new Notification(notification.title || "IntelliTwin Reminder", {
              body: notification.message || "You have an upcoming activity.",
              tag: `intellitwin-${id}`,
            });
          } catch (error) {
            console.warn("[Notifications] Desktop notification failed:", error);
          }
        }
      }

      if (freshNotifications.length) {
        setVisibleNotifications((current) => {
          const currentIds = new Set(current.map((item) => item._id));
          return [
            ...current,
            ...freshNotifications.filter((item) => !currentIds.has(item._id)),
          ].slice(-4);
        });
      }
    } catch (error) {
      console.warn("[Notifications] Failed to check notifications:", error);
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    checkNotifications();
    const interval = setInterval(checkNotifications, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [token, checkNotifications]);

  const markRead = useCallback(async (notificationId) => {
    if (!token || !notificationId) return;
    try {
      await api.post(`/notifications/${notificationId}/read`, {}, token);
    } catch (error) {
      console.warn("[Notifications] Failed to mark notification as read:", error);
    }
  }, [token]);

  const dismiss = useCallback(async (notification) => {
    await markRead(notification._id);
    setVisibleNotifications((current) => current.filter((item) => item._id !== notification._id));
  }, [markRead]);

  const openMissionControl = useCallback(async (notification) => {
    await dismiss(notification);
    router.push("/dashboard");
  }, [dismiss, router]);

  if (!token) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex w-[min(92vw,380px)] flex-col gap-3">
      {permission === "default" && typeof window !== "undefined" && "Notification" in window ? (
        <div className="rounded-xl border border-ink-600 bg-ink-900 p-3 shadow-xl">
          <p className="text-sm text-text">Enable desktop reminders?</p>
          <p className="mt-1 text-xs text-text-dim">You can still receive in-app reminders without enabling them.</p>
          <button
            type="button"
            onClick={requestPermission}
            className="mt-2 rounded-lg border border-ink-500 px-3 py-1.5 text-xs text-text hover:bg-ink-800"
          >
            Enable notifications
          </button>
        </div>
      ) : null}

      {visibleNotifications.map((notification) => (
        <div key={notification._id} className="rounded-xl border border-ink-600 bg-ink-900 p-4 shadow-2xl">
          <p className="text-sm font-medium text-text">
            {notification.title || "IntelliTwin Reminder"}
          </p>
          <p className="mt-1 text-sm leading-5 text-text-dim">
            {notification.message || "You have an upcoming activity."}
          </p>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => openMissionControl(notification)}
              className="rounded-lg bg-cyan-300 px-3 py-1.5 text-xs font-medium text-slate-950"
            >
              Open Mission Control
            </button>
            <button
              type="button"
              onClick={() => dismiss(notification)}
              className="rounded-lg border border-ink-500 px-3 py-1.5 text-xs text-text-dim hover:bg-ink-800"
            >
              Dismiss
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
