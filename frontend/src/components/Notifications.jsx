import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Empty, ErrorBox, Spinner, formatDate } from "./ui.jsx";
import { useEffect, useRef } from "react";

/* ---------- Drawer (unchanged behaviour) ---------- */
export function Drawer({
  open,
  onClose,
  title,
  side = "right",
  id,
  closeLabel = "Close",
  children,
}) {
  const closeRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const trigger = document.activeElement;
    const onKey = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      if (trigger instanceof HTMLElement) trigger.focus();
    };
  }, [open, onClose]);

  return (
    <>
      <div
        className={`sheet-backdrop${open ? " open" : ""}`}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        id={id}
        className={`sheet sheet-${side}${open ? " open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        aria-hidden={!open}
        inert={!open ? "" : undefined}
      >
        <div className="sheet-head">
          <h2>{title}</h2>
          <button ref={closeRef} className="icon-btn" onClick={onClose} aria-label={closeLabel}>
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
              <path
                d="M6 6l12 12M18 6L6 18"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                fill="none"
              />
            </svg>
          </button>
        </div>
        <div className="sheet-body">{children}</div>
      </aside>
    </>
  );
}

/* ---------- helpers ---------- */
function KindIcon({ kind }) {
  const common = {
    viewBox: "0 0 24 24",
    width: 22,
    height: 22,
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.9,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true",
  };
  if (kind === "outcome_reminder") {
    // clipboard with check
    return (
      <svg {...common}>
        <rect x="5" y="4" width="14" height="17" rx="2" />
        <path d="M9 4h6v3H9z" />
        <path d="M9 14l2 2 4-4" />
      </svg>
    );
  }
  // default: bell
  return (
    <svg {...common}>
      <path d="M6 16V11a6 6 0 1112 0v5l1.5 2h-15L6 16z" />
      <path d="M10 21h4" />
    </svg>
  );
}

function timeAgo(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const seconds = Math.round((date.getTime() - Date.now()) / 1000);
  const units = [
    ["year", 31536000],
    ["month", 2592000],
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit);
  }
  return rtf.format(0, "second");
}

/* ---------- Notification list ---------- */
export function NotificationList({ onNavigate }) {
  const { t } = useAuth();
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["notifications"], queryFn: () => api("/notifications/") });
  const refresh = () => client.invalidateQueries({ queryKey: ["notifications"] });

  const read = useMutation({
    mutationFn: (id) => api(`/notifications/${id}/read/`, { method: "POST" }),
    onSuccess: refresh,
  });
  const readAll = useMutation({
    mutationFn: (ids) =>
      Promise.all(ids.map((id) => api(`/notifications/${id}/read/`, { method: "POST" }))),
    onSuccess: refresh,
  });

  if (query.isLoading) return <Spinner />;
  if (query.isError) return <ErrorBox>{query.error.message}</ErrorBox>;

  const notifications = query.data.results || [];
  if (!notifications.length) return <Empty>{t("notifications_empty")}</Empty>;

  const unreadIds = notifications.filter((n) => !n.read_at).map((n) => n.id);

  return (
    <div className="notif">
      <div className="notif-toolbar">
        <p className="text-paper" aria-live="polite">
          {unreadIds.length > 0
            ? `${unreadIds.length} ${t("notification_new")}`
            : t("notification_all_caught_up")}
        </p>
        {unreadIds.length > 1 && (
          <button
            type="button"
            className="notif-link"
            disabled={readAll.isPending}
            onClick={() => readAll.mutate(unreadIds)}
          >
            {t("notification_mark_all_read")}
          </button>
        )}
      </div>

      <ul className="notif-list">
        {notifications.map((item) => {
          const unread = !item.read_at;
          const isOutcome = item.kind === "outcome_reminder";
          return (
            <li key={item.id}>
              <article className={`notif-card${unread ? " unread" : ""}`}>
                <span className={`notif-icon kind-${item.kind}`}>
                  <KindIcon kind={item.kind} />
                </span>

                <div className="notif-main">
                  <div className="notif-top">
                    <h3 className="notif-title">{t(`notification_${item.kind}`)}</h3>
                  </div>
                  <time
                    className="notif-time"
                    dateTime={item.created_at}
                    title={formatDate(item.created_at)}
                  >
                    {timeAgo(item.created_at)}
                  </time>

                  {(isOutcome || unread) && (
                    <div className="notif-actions">
                      {isOutcome && (
                        <Link
                          className="notif-cta"
                          to={`/outcome/${item.payload.session_id}`}
                          onClick={() => {
                            if (unread) read.mutate(item.id);
                            onNavigate?.();
                          }}
                        >
                          {t("notification_open_outcome")}
                        </Link>
                      )}
                      {unread && (
                        <button
                          type="button"
                          className="notif-link"
                          disabled={read.isPending}
                          onClick={() => read.mutate(item.id)}
                        >
                          {t("notification_mark_read")}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </article>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function Notifications() {
  const { t } = useAuth();
  return (
    <section className="page-review">
      <h1>{t("notifications_title")}</h1>
      <NotificationList />
    </section>
  );
}