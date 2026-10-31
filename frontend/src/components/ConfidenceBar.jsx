import { useAuth } from "../auth.jsx";

export default function ConfidenceBar({ confidence = 0, band }) {
  const { t } = useAuth();
  const numeric = Math.max(0, Math.min(1, Number(confidence) || 0));
  const rounded = Math.round((numeric * 100) / 5) * 5;
  const bandKey = ({ "very likely": "result_band_very_likely", likely: "result_band_likely", possible: "result_band_possible", unlikely: "result_band_unlikely" })[band?.toLowerCase()] || "result_band_possible";
  return <div className="confidence-wrap">
    <p className="confidence-headline">{t(bandKey)}</p>
    <div className="confidence-track" role="img" aria-label={t(bandKey)}>
      <span className="confidence-fill" style={{ width: `${numeric * 100}%` }} />
    </div>
    <span className="muted small confidence-number">{t("result_confidence_approx", { number: rounded })}</span>
  </div>;
}
