"use client";

import { useEffect, useState } from "react";

import { listNotifications, markNotificationRead, type Notification } from "@/lib/collab";

export function NotificationsDrawer() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);

  useEffect(() => {
    if (!open) return;
    listNotifications(false).then(setItems);
  }, [open]);

  async function onClick(n: Notification) {
    if (!n.read_at) await markNotificationRead(n.id);
    setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x)));
  }

  const unreadCount = items.filter((i) => !i.read_at).length;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((x) => !x)}
        className="relative rounded-full p-2 text-warm-fog hover:bg-warm-fog/10"
        aria-label="Notifications"
      >
        🔔
        {unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-warn px-1 text-[0.65rem] text-carbon">
            {unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-80 overflow-hidden rounded-lg bg-warm-fog/5 shadow-xl ring-1 ring-warm-fog/10">
          <div className="max-h-96 overflow-y-auto">
            {items.length === 0 ? (
              <p className="p-4 text-sm text-warm-fog/60">No notifications</p>
            ) : (
              <ul>
                {items.map((n) => (
                  <li
                    key={n.id}
                    onClick={() => onClick(n)}
                    className={`cursor-pointer border-b border-warm-fog/10 p-3 text-sm ${
                      n.read_at ? "opacity-60" : ""
                    }`}
                  >
                    <p className="text-warm-fog">
                      <span className="text-aether-teal">{n.kind}</span>{" "}
                      &mdash; {JSON.stringify(n.payload).slice(0, 120)}
                    </p>
                    <p className="text-xs text-warm-fog/40">{new Date(n.created_at).toLocaleString()}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
