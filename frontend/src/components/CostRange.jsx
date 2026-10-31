import { formatDate, pkr } from "./ui.jsx";
import { useAuth } from "../auth.jsx";

export default function CostRange({ cost }) {
  const { t } = useAuth();
  if (!cost) return <section className="cost-range panel"><h4>{t("result_cost_title")}</h4><p>{t("result_cost_unavailable")}</p><p className="estimate-label">{t("result_estimate_unverified")}</p></section>;
  return <section className="cost-range panel" aria-label={t("result_cost_title")}>
    <h4>{t("result_cost_title")}</h4>
    <p className="muted small">{t("result_cost_city", { city: cost.city || t("result_city_unknown") })}</p>
    <div className="cost-parts">
      <span>{t("result_parts")}</span><strong>{pkr(cost.parts_min)} – {pkr(cost.parts_max)}</strong>
      <span>{t("result_labour")}</span><strong>{pkr(cost.labour_min)} – {pkr(cost.labour_max)}</strong>
      <span>{t("result_total")}</span><strong>{pkr(cost.total_min)} – {pkr(cost.total_max)}</strong>
    </div>
    {cost.last_verified
      ? <p className="muted small">{t("result_last_verified", { date: formatDate(cost.last_verified) })}</p>
      : <p className="estimate-label">{t("result_estimate_unverified")}</p>}
  </section>;
}
