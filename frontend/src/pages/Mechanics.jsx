import { useEffect, useState } from "react";
import { api, getAll } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Empty, ErrorBox, Field, Spinner, formatDate, useLoad } from "../components/ui.jsx";

const REVIEW_CRITERIA = [
  ["work_quality", "mechanics_review_work_quality"],
  ["price_fairness", "mechanics_review_price_fairness"],
  ["communication", "mechanics_review_communication"],
  ["timeliness", "mechanics_review_timeliness"],
];
const REVIEWS_PAGE = 5;

// Clamp so a bad value from the API can never throw in String.prototype.repeat.
const clampStars = (n) => Math.min(5, Math.max(0, Math.round(Number(n)) || 0));
const stars = (n) => {
  const r = clampStars(n);
  return "★".repeat(r) + "☆".repeat(5 - r);
};

// useLoad errors may be an Error, an ApiError with field data, or a plain string.
function errMsg(err) {
  if (!err) return "";
  if (typeof err === "string") return err;
  if (err.data && typeof err.data === "object") {
    const parts = Object.values(err.data)
      .flatMap((value) => (Array.isArray(value) ? value : [value]))
      .map(String);
    if (parts.length) return parts.join(" ");
  }
  return err.message || "";
}

// t() returns the key when a translation is missing; show readable English instead.
function useTr() {
  const { t } = useAuth();
  return (key, fallback) => {
    const v = t(key);
    return !v || v === key ? fallback : v;
  };
}

function useDebounced(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

function Stars({ value }) {
  const { t } = useAuth();
  return (
    <span className="stars" role="img" aria-label={t("mechanics_rating_aria", { rating: value })}>
      {stars(value)}
    </span>
  );
}

// Native radio inputs under the stars: keyboard arrows, form validation and screen readers for free.
function StarInput({ name, label, value, onChange }) {
  return (
    <fieldset className="star-input">
      <legend>{label}</legend>
      <div className="star-input-row">
        {[1, 2, 3, 4, 5].map((n) => (
          <label key={n} className={n <= value ? "on" : ""}>
            <input
              type="radio"
              name={name}
              value={n}
              checked={value === n}
              onChange={() => onChange(n)}
              required={n === 1}
              className="sr-only"
            />
            <span aria-hidden="true">★</span>
            <span className="sr-only">{n}/5</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/* ------------------------------------------------------------------ */
/* Review form: closed by default, opened with "Write a review"        */
/* ------------------------------------------------------------------ */
function ReviewDialog({ mechanic, onClose, onSubmitted }) {
  const { t } = useAuth();
  const tr = useTr();
  const [ratings, setRatings] = useState(Object.fromEntries(REVIEW_CRITERIA.map(([key]) => [key, 0])));
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const titleId = `review-title-${mechanic.user}`;

  // Escape closes (unless sending); background page doesn't scroll while open.
  useEffect(() => {
    const onKey = (event) => event.key === "Escape" && !busy && onClose();
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [onClose, busy]);

  async function submit(event) {
    event.preventDefault();
    if (busy) return; // block double submits
    setBusy(true);
    setError("");
    try {
      await api("/reviews/", {
        method: "POST",
        body: { mechanic: mechanic.user, ...ratings, comment: comment.trim() },
      });
      onSubmitted(); // parent closes the dialog
    } catch (err) {
      setError(errMsg(err));
      setBusy(false);
    }
  }

  return (
    <div
      className="records-backdrop"
      role="presentation"
      onClick={(event) => event.target === event.currentTarget && !busy && onClose()}
    >
      <form className="records-dialog panel stack" role="dialog" aria-modal="true" aria-labelledby={titleId} onSubmit={submit}>
        <div className="section-head">
          <div>
            <h2 id={titleId}>{t("mechanics_review_title")}</h2>
            <p className="muted small">{mechanic.workshop_name}</p>
          </div>
          <button type="button" className="btn ghost" aria-label={tr("close", "Close")} onClick={onClose} disabled={busy}>
            ✕
          </button>
        </div>
        <p className="muted small">{t("mechanics_review_guidance")}</p>

        {REVIEW_CRITERIA.map(([key, label]) => (
          <StarInput
            key={key}
            name={key}
            label={t(label)}
            value={ratings[key]}
            onChange={(n) => setRatings((current) => ({ ...current, [key]: n }))}
          />
        ))}

        <Field label={t("mechanics_review_comment")}>
          <textarea rows={3} maxLength={2000} value={comment} onChange={(e) => setComment(e.target.value)} />
        </Field>
        <p className="muted small" aria-live="polite">{comment.length}/2000</p>

        <ErrorBox>{error}</ErrorBox>
        <div className="row">
          <button className="btn" disabled={busy}>
            {busy ? t("saving") : t("mechanics_post_review")}
          </button>
          <button type="button" className="btn ghost" onClick={onClose} disabled={busy}>
            {t("cancel")}
          </button>
        </div>
      </form>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Expanded details. Mounted only when the card is open, so reviews    */
/* are fetched on demand instead of once per mechanic in the list.     */
/* ------------------------------------------------------------------ */
function MechanicDetails({ mechanic }) {
  const { t } = useAuth();
  const tr = useTr();
  const list = useLoad(() => getAll(`/reviews/?mechanic=${mechanic.user}`), [mechanic.user]);
  const [writing, setWriting] = useState(false);
  const [sent, setSent] = useState(false);
  const [limit, setLimit] = useState(REVIEWS_PAGE);

  const reviews = (list.data || []).filter((review) => review.status !== "rejected");
  const visible = reviews.slice(0, limit);

  return (
    <div className="mechanic-details" id={`mechanic-details-${mechanic.user}`}>
      <h3>{t("mechanics_shop_details")}</h3>
      <p><strong>{t("mechanics_address")}:</strong> {mechanic.address || t("mechanics_not_provided")}</p>
      <p><strong>{t("city")}:</strong> {mechanic.city || t("mechanics_not_provided")}</p>
      <p>
        <strong>{t("mechanics_phone")}:</strong>{" "}
        {mechanic.phone ? <a href={`tel:${mechanic.phone}`}>{mechanic.phone}</a> : t("mechanics_not_provided")}
      </p>

      <div className="section-head">
        <h3>{t("mechanics_latest_reviews")}</h3>
        {!sent && (
          <button type="button" className="btn" onClick={() => setWriting(true)}>
            {tr("mechanics_write_review", "Write a review")}
          </button>
        )}
      </div>

      {sent && <p className="ok-text" role="status">{t("mechanics_review_thanks")}</p>}

      {list.loading && <Spinner />}
      {list.error && (
        <>
          <ErrorBox>{errMsg(list.error)}</ErrorBox>
          <button className="btn ghost" type="button" onClick={list.reload}>{t("retry")}</button>
        </>
      )}
      {!list.loading && !list.error && reviews.length === 0 && (
        <p className="muted small">{t("mechanics_no_reviews")}</p>
      )}

      {visible.length > 0 && (
        <ul className="plain">
          {visible.map((r) => (
            <li key={r.id} className="review">
              <div>
                <Stars value={r.rating} /> <strong>{r.reviewer_name}</strong>
                <span className="muted small"> {formatDate(r.created_at)}</span>
                {r.status === "pending" && <span className="chip"> {t("mechanics_review_pending")}</span>}
              </div>
              {REVIEW_CRITERIA.some(([key]) => r[key] != null) && (
                <ul className="plain review-criteria">
                  {REVIEW_CRITERIA.filter(([key]) => r[key] != null).map(([key, label]) => (
                    <li key={key}>{t(label)}: {r[key]}/5</li>
                  ))}
                </ul>
              )}
              {r.comment && <div>{r.comment}</div>}
            </li>
          ))}
        </ul>
      )}

      {reviews.length > limit && (
        <button type="button" className="link-btn" onClick={() => setLimit((n) => n + REVIEWS_PAGE)}>
          {tr("show_more", "Show more")} ({reviews.length - limit})
        </button>
      )}

      {writing && (
        <ReviewDialog
          mechanic={mechanic}
          onClose={() => setWriting(false)}
          onSubmitted={() => {
            setWriting(false);
            setSent(true);
            list.reload();
          }}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */
export default function Mechanics() {
  const { t } = useAuth();
  const [q, setQ] = useState("");
  const search = useDebounced(q.trim()); // one request per pause in typing, not per keystroke
  const [open, setOpen] = useState(null);
  const list = useLoad(
    () => api(`/accounts/mechanics/?search=${encodeURIComponent(search)}`).then((d) => d.results ?? d),
    [search]
  );

  return (
    <>
      <h1>{t("nav_mechanics")}</h1>
      <Field label={t("mechanics_search_label")}>
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} autoComplete="off" />
      </Field>
      {list.loading && <Spinner />}
      {list.error && <ErrorBox>{errMsg(list.error)}</ErrorBox>}
      {list.data?.length === 0 && <Empty>{t("mechanics_no_match")}</Empty>}

      {(list.data || []).map((m) => {
        const isOpen = open === m.user;
        return (
          <article key={m.user} className="panel">
            <h2>{m.workshop_name}</h2>
            <p className="muted">
              {m.city || t("mechanics_city_missing")}. {m.specialization || t("mechanics_general_repairs")}.{" "}
              {t("mechanics_experience", { years: m.experience_years })}
            </p>
            <p>
              {m.review_count > 0 ? (
                <>
                  <Stars value={m.average_rating} />{" "}
                  {t(m.review_count === 1 ? "mechanics_rating_summary_one" : "mechanics_rating_summary", {
                    rating: m.average_rating,
                    count: m.review_count,
                  })}
                </>
              ) : (
                t("mechanics_no_reviews")
              )}
              {m.is_verified && <span className="chip ok">{t("mechanics_verified")}</span>}
            </p>

            {isOpen && <MechanicDetails mechanic={m} />}

            <button
              className="btn ghost"
              type="button"
              aria-expanded={isOpen}
              aria-controls={isOpen ? `mechanic-details-${m.user}` : undefined}
              onClick={() => setOpen(isOpen ? null : m.user)}
            >
              {t(isOpen ? "mechanics_read_less" : "mechanics_read_more")}
            </button>
          </article>
        );
      })}
    </>
  );
}