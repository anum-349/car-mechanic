import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import { Empty, ErrorBox, Spinner, formatDate } from "../components/ui.jsx";
import { sessionTarget, useCars, useCategories, useSessions } from "../api/quries.js";

export default function History() {
  const { t, pick } = useAuth();

  // t() returns the key when a translation is missing; show readable English instead.
  const tr = (key, fallback) => {
    const v = t(key);
    return !v || v === key ? fallback : v;
  };

  // Filter + page live in the URL, so refresh / back button / shared links keep them.
  const [params, setParams] = useSearchParams();
  const carId = params.get("car") || "";
  const page = Math.max(1, Number(params.get("page")) || 1);

  const update = (next) =>
    setParams((prev) => {
      const p = new URLSearchParams(prev);
      Object.entries(next).forEach(([key, value]) => {
        if (value === "" || value == null || (key === "page" && value === 1)) p.delete(key);
        else p.set(key, String(value));
      });
      return p;
    });

  // Sessions are required; cars and categories only enrich the rows, so their failure is non-fatal.
  const query = useSessions(carId, page);
  const carsQ = useCars();
  const catsQ = useCategories();
  const cars = carsQ.data; // undefined while loading or if the request failed
  const cats = catsQ.data ?? [];

  const carName = (c) => c.nickname || c.car_model_label;
  const carOf = (id) => cars?.find((item) => item.id === id);
  const titleOf = (s) => {
    if (s.obd_code) return s.obd_code;
    const cat = cats.find((item) => item.id === s.category);
    return cat ? pick(cat, "name") : t("history_diagnosis");
  };

  if (query.isLoading) return <Spinner />;

  if (query.isError) {
    return (
      <section className="history-page">
        <h1>{t("nav_history")}</h1>
        <ErrorBox>{query.error.message}</ErrorBox>
        {/* A stale ?page= or ?car= in the URL is a common cause (e.g. page out of range). */}
        {(page > 1 || carId) && (
          <button type="button" className="btn ghost" onClick={() => setParams({})}>
            {tr("history_reset", "Reset filters")}
          </button>
        )}
      </section>
    );
  }

  const sessions = query.data?.results ?? [];
  const count = query.data?.count ?? 0;

  return (
    <section className="history-page">
      <h1>{t("nav_history")}</h1>

      {cars && cars.length > 0 && (
        <label className="history-filter">
          {t("history_car_filter")}
          <select value={carId} onChange={(e) => update({ car: e.target.value, page: 1 })}>
            <option value="">{t("history_all_cars")}</option>
            {cars.map((item) => (
              <option value={item.id} key={item.id}>
                {carName(item)}
              </option>
            ))}
          </select>
        </label>
      )}

      {!sessions.length && (
        <Empty action={<Link className="btn" to="/diagnose">{t("start_diag")}</Link>}>
          {t("no_recent")}
        </Empty>
      )}

      {/* While a new page/filter loads, the previous data stays visible but dimmed. */}
      <ul className="list" aria-busy={query.isPlaceholderData} style={query.isPlaceholderData ? { opacity: 0.6 } : undefined}>
        {sessions.map((session) => {
          const car = carOf(session.car);
          const top = session.results?.[0];
          return (
            <li key={session.id}>
              <Link to={sessionTarget(session)} className="list-row stack-tight">
                <span>
                  <strong>{titleOf(session)}</strong>{" "}
                  <span className="muted small">{formatDate(session.started_at)}</span>
                </span>
                {cars && (
                  <span className="muted small">
                    {car ? carName(car) : t("history_car_removed")}
                  </span>
                )}
                {top && (
                  <span>
                    {top.cause_name}, {Math.round(Number(top.confidence) * 100)}% {t("likelihood")}
                  </span>
                )}
                <span>
                  <span className={`chip ${session.status}`}>
                    {tr(`history_status_${session.status}`, session.status)}
                  </span>
                  {session.safety_alert && <span className="chip bad">{t("safety_alert")}</span>}
                </span>
                {session.status === "completed" && !session.has_outcome && (
                  <span className="small">{t("history_add_outcome")}</span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>

      <div className="row history-pagination">
        <button
          type="button"
          className="btn ghost"
          disabled={!query.data?.previous}
          onClick={() => update({ page: page - 1 })}
        >
          {t("history_previous")}
        </button>
        <span>{t("history_page", { page, count })}</span>
        <button
          type="button"
          className="btn ghost"
          disabled={!query.data?.next}
          onClick={() => update({ page: page + 1 })}
        >
          {t("history_next")}
        </button>
      </div>
    </section>
  );
}