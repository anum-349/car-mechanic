import { useRef, useState } from "react";
import { toBlob } from "html-to-image";
import { useAuth } from "../auth.jsx";
import { trackEvent } from "../api.js";
import { pkr } from "./ui.jsx";

export default function ShareCard({ result, topCause, heading }) {
  const { t } = useAuth();
  const cardRef = useRef(null);
  const [sharing, setSharing] = useState(false);
  const [error, setError] = useState("");
  const cost = topCause?.cost;

  async function exportCard() {
    if (!cardRef.current) return;
    trackEvent("share_clicked", result.id, { share_target: navigator.share ? "native" : "download" });
    setSharing(true);
    setError("");
    try {
      const blob = await toBlob(cardRef.current, { pixelRatio: 2, cacheBust: true, skipFonts: true });
      if (!blob) throw new Error(t("result_share_failed"));
      const file = new File([blob], "gaari-diagnosis.png", { type: "image/png" });
      if (navigator.share && navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: t("result_share_title") });
      } else {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "gaari-diagnosis.png";
        link.click();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
    } catch (shareError) {
      if (shareError.name !== "AbortError") setError(t("result_share_failed"));
    } finally {
      setSharing(false);
    }
  }

  return <>
    <div className="share-card-offscreen" aria-hidden="true">
      <article className="share-card" ref={cardRef} data-testid="share-card" style={{ width: 360 }}>
        <p className="share-brand">{t("brand")}</p>
        <h2>{heading || t("result_share_verdict")}</h2>
        <p>{topCause?.cause_name || result.verdict || t("result_share_no_cause")}</p>
        {topCause && <p className="share-band">{t(({ "very likely": "result_band_very_likely", likely: "result_band_likely", possible: "result_band_possible", unlikely: "result_band_unlikely" })[topCause.band?.toLowerCase()] || "result_band_possible")}</p>}
        {cost && <p>{t("result_total")}: {pkr(cost.total_min)} – {pkr(cost.total_max)}</p>}
        <p className="share-referral">{t("result_referral", { code: "GC-0000" })}</p>
        <small>{t("result_share_watermark")}</small>
      </article>
    </div>
    <button className="btn" type="button" onClick={exportCard} disabled={sharing}>{sharing ? t("result_sharing") : t("result_share")}</button>
    {error && <p className="error" role="alert">{error}</p>}
  </>;
}
