import { useQuery } from "@tanstack/react-query";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { ErrorBox, Spinner } from "../components/ui.jsx";

function BarChart({ rows, labelKey, valueKey, title }) {
  const max = Math.max(1, ...rows.map((row) => Number(row[valueKey] || 0)));
  return <section className="panel analytics-chart">
    <h2>{title}</h2>
    {rows.length > 0 && <div className="analytics-bars">
      {rows.map((row, index) => {
        const value = Number(row[valueKey] || 0);
        return <div className="analytics-bar-row" key={`${row[labelKey]}-${index}`}>
          <span title={row[labelKey]}>{row[labelKey]}</span>
          <svg viewBox="0 0 220 20" role="img" aria-label={`${row[labelKey]}: ${value}`}>
            <rect x="0" y="2" width="220" height="16" rx="4" fill="var(--subtle-surface, #e8edf3)" />
            <rect x="0" y="2" width={Math.max(value ? 3 : 0, 220 * value / max)} height="16" rx="4" fill="var(--accent, #2463eb)" />
            <text x={Math.min(206, 220 * value / max + 6)} y="14" fontSize="11" fill="currentColor">{value}</text>
          </svg>
        </div>;
      })}
    </div>}
  </section>;
}

function Metric({ label, value, percent = false }) {
  const shown = percent ? `${(Number(value || 0) * 100).toFixed(1)}%` : Number(value || 0).toFixed(2);
  return <article className="panel analytics-metric"><span className="muted">{label}</span><strong>{shown}</strong></article>;
}

export default function AnalyticsDashboard() {
  const { t } = useAuth();
  const query = useQuery({ queryKey: ["admin-analytics"], queryFn: () => api("/admin/analytics/") });
  if (query.isLoading) return <Spinner />;
  if (query.isError) return <ErrorBox>{query.error.message}</ErrorBox>;
  const data = query.data;
  const categories = data.top_categories.map((row) => ({ ...row, label: row.category, value: row.sessions }));
  const questions = data.question_dropoff.slice(0, 10).map((row) => ({
    ...row,
    label: `${row.question_id ?? "?"}: ${row.question}`,
    value: row.asked_then_abandoned,
  }));
  return <section className="analytics-dashboard">
    <h1>{t("analytics_title")}</h1>
    <p className="muted">{t("analytics_period", { days: data.period_days })}</p>
    <div className="analytics-metrics">
      <Metric label={t("analytics_average_questions")} value={data.average_questions_per_session} />
      <Metric label={t("analytics_share_rate")} value={data.share_rate} percent />
      <Metric label={t("analytics_outcome_rate")} value={data.outcome_rate} percent />
      <Metric label={t("analytics_top3")} value={data.top3_accuracy} percent />
      <Metric label={t("analytics_cost_hit")} value={data.cost_range_hit_rate} percent />
      <Metric label={t("analytics_safety")} value={data.safety_stop_count} />
    </div>
    <BarChart rows={data.sessions_per_day.map((row) => ({ ...row, day: row.day, sessions: row.value }))}
      labelKey="day" valueKey="sessions" title={t("analytics_sessions")} />
    <BarChart rows={categories} labelKey="label" valueKey="value" title={t("analytics_categories")} />
    <BarChart rows={questions} labelKey="label" valueKey="value" title={t("analytics_dropoff")} />
    <ul className="analytics-counts">{data.question_dropoff.slice(0, 10).map((row) => <li key={row.question_id}>
      <span>{row.question}</span><span>{t("analytics_asked")}: {row.asked} · {t("analytics_answered")}: {row.answered} · {t("analytics_abandoned")}: {row.asked_then_abandoned}</span>
    </li>)}</ul>
  </section>;
}
