import { useCallback, useEffect, useState } from "react";
import { NavLink, Link, useLocation } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api.js";
import ThemeToggle from "./ThemeToggle.jsx";
import { Drawer, NotificationList } from "./Notifications.jsx";
import "./layout.css";

const LANGS = [
  { code: "en", label: "English" },
  { code: "roman_ur", label: "Roman Urdu" },
];

const CAR_OWNER = [
  { to: "/", key: "nav_home", end: true },
  { to: "/diagnose", key: "nav_diagnose" },
  { to: "/garage", key: "nav_garage" },
  { to: "/scam-shield", key: "nav_quote" },
  { to: "/mechanics", key: "nav_mechanics" },
];
const CAR_OWNER_MORE = [
  { to: "/history", key: "nav_history" },
  { to: "/warning-lights", key: "nav_lights" },
  { to: "/obd", key: "nav_obd" },
];
const MECHANIC = [
  { to: "/mechanic", key: "mechanic_nav", end: true },
  { to: "/mechanic/records", key: "mechanic_records_nav" },
  { to: "/mechanic/simulator", key: "mechanic_simulator_nav" },
  { to: "/mechanic/ai-drafts", key: "mechanic_ai_drafts_nav" },
];
const MECHANIC_MORE = [
  { to: "/diagnose", key: "nav_diagnose" },
  { to: "/garage", key: "nav_garage" },
  { to: "/scam-shield", key: "nav_quote" },
  { to: "/mechanics", key: "nav_mechanics" },
  { to: "/history", key: "nav_history" },
  { to: "/warning-lights", key: "nav_lights" },
  { to: "/obd", key: "nav_obd" },
]
const REVIEW = { to: "/review", key: "review_title" };
const ANALYTICS = { to: "/admin/analytics", key: "analytics_title" };

// One entry per role: where the brand links to, what shows in the topbar / bottom
// tabs (primary), and what lives in the sidebar (secondary). Edit here to change a role's nav.
const NAV_BY_ROLE = {
  mechanic: { home: "/mechanic", primary: MECHANIC, secondary: MECHANIC_MORE },
  reviewer: { home: "/review", primary: [REVIEW], secondary: [] },
  admin: { home: "/review", primary: [REVIEW, ANALYTICS], secondary: [] },
};
const DEFAULT_NAV = { home: "/", primary: CAR_OWNER, secondary: CAR_OWNER_MORE };

function BellIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.7 21a2 2 0 0 1-3.4 0" />
    </svg>
  );
}

function MenuIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M3 6h18M3 12h18M3 18h18" />
    </svg>
  );
}

function LangSwitch({ lang, setLang }) {
  return (
    <div className="seg grid grid-cols-2" role="group" aria-label="Language">
      {LANGS.map((l) => (
        <button
          key={l.code}
          className={lang === l.code ? "on" : ""}
          aria-pressed={lang === l.code}
          onClick={() => setLang(l.code)}
        >
          {l.code === "en" ? "English" : "Roman"}
        </button>
      ))}
    </div>
  );
}

export default function Layout({ children }) {
  const { t, lang, setLang, logout, user } = useAuth();
  const [open, setOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const closeNotif = useCallback(() => setNotifOpen(false), []);
  const { pathname } = useLocation();

  const { home, primary, secondary } = NAV_BY_ROLE[user?.role] || DEFAULT_NAV;

  const notifications = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api("/notifications/"),
    enabled: Boolean(user),
    refetchInterval: 60000,
  });
  const unread = notifications.data?.unread_count || 0;

  // Close both drawers on navigation.
  useEffect(() => {
    setOpen(false);
    setNotifOpen(false);
  }, [pathname]);

  // Escape to close + lock body scroll while the nav sidebar is open.
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open]);

  return (
    <div className="shell">
      <header className="topbar">
        {/* On desktop the menu button only appears for roles that have sidebar links. */}
        {
          user?.role != 'admin' ?
            <button
              className={`icon-btn menu-btn${secondary.length ? "" : " no-links"}`}
              onClick={() => setOpen(true)}
              aria-label={t("menu") || "Menu"}
              aria-expanded={open}
              aria-controls="side-drawer"
            >
              <MenuIcon />
            </button> : null
        }

        <Link to={home} className="brand">{t("brand")}</Link>

        <nav className="topnav" aria-label="Main">
          {primary.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end}>{t(l.key)}</NavLink>
          ))}
        </nav>

        <div className="topbar-tools">
          <span className="hide-mobile"><ThemeToggle /></span>
          <button
            type="button"
            className="icon-btn notification-link"
            onClick={() => {
              setOpen(false);
              setNotifOpen(true);
            }}
            aria-haspopup="dialog"
            aria-expanded={notifOpen}
            aria-controls="notifications-drawer"
            aria-label={
              unread ? `${t("notifications_title")} (${unread})` : t("notifications_title")
            }
          >
            <BellIcon />
            {unread > 0 && (
              <span className="notification-badge">{unread > 99 ? "99+" : unread}</span>
            )}
          </button>
          <span className="hide-mobile"><LangSwitch lang={lang} setLang={setLang} /></span>
          <button className="link-btn hide-mobile" onClick={logout} title={user?.username}>
            {t("logout")}
          </button>
        </div>
      </header>

      {/* Sidebar */}
      <div
        className={`drawer-backdrop${open ? " open" : ""}`}
        onClick={() => setOpen(false)}
        aria-hidden="true"
      />
      <aside
        id="side-drawer"
        className={`drawer${open ? " open" : ""}`}
        aria-label="More navigation"
        aria-hidden={!open}
        inert={!open ? "" : undefined}
      >
        <div className="drawer-head">
          <span className="brand">{t("brand")}</span>
          <button className="icon-btn" onClick={() => setOpen(false)} aria-label="Close menu">
            ✕
          </button>
        </div>

        {secondary.length > 0 && (
          <nav className="drawer-nav">
            {secondary.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end}>{t(l.key)}</NavLink>
            ))}
          </nav>
        )}

        <div className="drawer-foot show-mobile">
          <ThemeToggle />
          <LangSwitch lang={lang} setLang={setLang} />
          <button className="link-btn" onClick={logout}>
            {t("logout")}{user?.username ? ` (${user.username})` : ""}
          </button>
        </div>
      </aside>

      <Drawer
        id="notifications-drawer"
        open={notifOpen}
        onClose={closeNotif}
        title={t("notifications_title")}
        side="right"
      >
        <NotificationList onNavigate={closeNotif} />
      </Drawer>

      <main className="page">{children}</main>

      <nav className="tabbar" aria-label="Main">
        {primary.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end}>{t(l.key)}</NavLink>
        ))}
      </nav>
    </div>
  );
}