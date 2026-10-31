import { Link } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import { Empty, ErrorBox, Spinner, formatDate } from "../components/ui.jsx";
import { sessionTarget, useCars, useCategories, useSessions } from "../api/quries.js";

const RECENT_LIMIT = 3;

export default function Home() {
  const { user, t, pick } = useAuth();

  // t() returns the key when a translation is missing; show readable English instead.
  const tr = (key, fallback) => {
    const v = t(key);
    return !v || v === key ? fallback : v;
  };

  // Sessions are core to this page; cars and categories are secondary and must not block it.
  const sessionsQ = useSessions();
  const carsQ = useCars();
  const catsQ = useCategories();

  const all = sessionsQ.data?.results ?? [];
  const total = sessionsQ.data?.count ?? all.length;
  const recent = all.slice(0, RECENT_LIMIT);
  const cars = carsQ.data; // undefined while loading or if the request failed
  const cats = catsQ.data ?? [];
  const hasNoCars = Array.isArray(cars) && cars.length === 0;

  const carName = (c) => c.nickname || c.car_model_label;
  const carOf = (id) => cars?.find((c) => c.id === id);

  const titleOf = (s) => {
    if (s.obd_code) return s.obd_code;
    const cat = cats.find((x) => x.id === s.category);
    return cat ? pick(cat, "name") : t("history_diagnosis");
  };

  // The label tells the driver what tapping the row will do.
  const actionOf = (s) => {
    if (s.status !== "completed") return tr("action_continue", "Continue");
    return s.has_outcome
      ? tr("action_view_result", "View result")
      : tr("history_add_outcome", "Add outcome");
  };

  const active = all.find((s) => s.status === "in_progress");
  // Only surface an outcome card for sessions that are NOT already in the recent list.
  const needsOutcome = all.find(
    (s) => s.status === "completed" && !s.has_outcome && !recent.includes(s)
  );

  return (
    <>
      <p className="greeting">
        {tr("greeting", "Salam")}, {user?.name || user?.username}
      </p>

      <section className="hero">
        <h1>{t("hero_title")}</h1>
        <p>{t("hero_sub")}</p>
        {hasNoCars ? (
          <Link className="btn" to="/garage">
            {t("add_car_first")}
          </Link>
        ) : (
          <Link className="btn" to="/diagnose">
            {t("start_diag")}
          </Link>
        )}
      </section>

      {/* Safety: always one tap away */}
      <Link className="list-row danger" to="/stop-driving">
        <span>
          <strong>{tr("stop_driving_title", "Should I stop driving?")}</strong>
          <span className="muted small">
            {" "}
            {tr("stop_driving_sub", "Smoke, warning light, strange noise: check now")}
          </span>
        </span>
      </Link>

      {cars && cars.length > 0 && (
        <section>
          <h2>{tr("my_cars", "My cars")}</h2>
          <div className="chips">
            {cars.slice(0, 4).map((c) => (
              <Link key={c.id} className="chip" to="/garage">
                {carName(c)}
              </Link>
            ))}
            <Link className="chip" to="/garage">
              {tr("manage_garage", "Manage garage")}
            </Link>
          </div>
        </section>
      )}

      {/* Latest 3 diagnoses */}
      <section>
        <h2>{t("recent")}</h2>
        {sessionsQ.isLoading && <Spinner />}
        {sessionsQ.isError && <ErrorBox>{sessionsQ.error.message}</ErrorBox>}
        {sessionsQ.isSuccess && recent.length === 0 && (
          <Empty action={<Link className="btn" to="/diagnose">{t("start_diag")}</Link>}>
            {t("no_recent")}
          </Empty>
        )}

        {recent.length > 0 && (
          <ul className="list">
            {recent.map((s) => {
              const car = carOf(s.car);
              const top = s.results?.[0];
              return (
                <li key={s.id}>
                  <Link to={sessionTarget(s)} className="list-row stack-tight">
                    <span>
                      <strong>{titleOf(s)}</strong>
                      <span className="muted small"> {formatDate(s.started_at)}</span>
                    </span>
                    {cars && (
                      <span className="muted small">
                        {car ? carName(car) : t("history_car_removed")}
                      </span>
                    )}
                    {top && (
                      <span>
                        {top.cause_name}, {Math.round(Number(top.confidence) * 100)}%{" "}
                        {t("likelihood")}
                      </span>
                    )}
                    <span>
                      <span className={`chip ${s.status}`}>
                        {tr(`history_status_${s.status}`, s.status)}
                      </span>
                      {s.safety_alert && <span className="chip bad">{t("safety_alert")}</span>}
                    </span>
                    <span className="small">{actionOf(s)} →</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}

        {recent.length > 0 && (
          <p>
            <Link to="/history">
              {tr("view_all_history", "View all history")}
              {total > RECENT_LIMIT && ` (${total})`} →
            </Link>
          </p>
        )}
      </section>

      <section>
        <h2>{tr("tools", "Tools")}</h2>
        <ul className="list">
          <li>
            <Link className="list-row" to="/lights">
              <span>{t("nav_lights")}</span>
            </Link>
          </li>
          <li>
            <Link className="list-row" to="/obd">
              <span>{tr("nav_obd", "OBD code lookup")}</span>
            </Link>
          </li>
          <li>
            <Link className="list-row" to="/quote-check">
              <span>{t("check_quote")}</span>
            </Link>
          </li>
          <li>
            <Link className="list-row" to="/mechanics">
              <span>{t("nav_mechanics")}</span>
            </Link>
          </li>
        </ul>
      </section>
    </>
  );
}