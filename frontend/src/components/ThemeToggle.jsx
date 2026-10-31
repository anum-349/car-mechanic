import { useAuth } from "../auth.jsx";

export default function ThemeToggle() {
  const { t, theme, toggleTheme } = useAuth();
  return <button className="theme-toggle" type="button" onClick={toggleTheme}
    aria-label={t("theme_switch", { theme: theme === "dark" ? t("theme_light") : t("theme_dark") })}
    aria-pressed={theme === "dark"}>
    <span aria-hidden="true">{theme === "dark" ? "☀" : "☾"}</span>
    <span>{theme === "dark" ? t("theme_light") : t("theme_dark")}</span>
  </button>;
}
