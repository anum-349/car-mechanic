import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, getAll } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Empty, ErrorBox, Field, Spinner, formatDate, pkr } from "../components/ui.jsx";
import { carsKey, sessionsKey, useCars } from "../api/quries.js";

const TRANSMISSIONS = ["manual", "automatic", "cvt", "dct"];
const FUELS = ["petrol", "diesel", "hybrid", "electric", "cng"];
const SERVICE_SUGGESTIONS = [
  "Oil change",
  "General service",
  "Brake pads",
  "Tyres",
  "Battery",
  "AC service",
  "Coolant flush",
  "Spark plugs",
  "Air filter",
  "Timing belt",
];
const thisYear = new Date().getFullYear();

const serviceLogsKey = (carId) => ["service-logs", carId];

// Local calendar date (not UTC), so late-night entries in UTC+5 don't land on yesterday.
const today = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);

function numberInputValue(value) {
  if (value === "" || value == null || !Number.isFinite(Number(value))) return "";
  return value;
}

function parseErrors(error) {
  if (error?.data && typeof error.data === "object") {
    return Object.fromEntries(
      Object.entries(error.data).map(([key, value]) => [key, Array.isArray(value) ? value.join(" ") : String(value)])
    );
  }
  return { form: error?.message || "Something went wrong" };
}

function FieldError({ message }) {
  return message ? <span className="field-error" role="alert">{message}</span> : null;
}

// t() returns the key when a translation is missing; show readable English instead.
function useTr() {
  const { t } = useAuth();
  return (key, fallback) => {
    const v = t(key);
    return !v || v === key ? fallback : v;
  };
}

/* ------------------------------------------------------------------ */
/* Add / edit car (exported: other pages may embed it)                 */
/* ------------------------------------------------------------------ */
export function AddCar({ car, onCancel, onSaved }) {
  const { t } = useAuth();
  const queryClient = useQueryClient();
  const makeQuery = useQuery({ queryKey: ["car-makes"], queryFn: () => getAll("/garage/makes/") });
  const [make, setMake] = useState("");
  const [form, setForm] = useState({
    car_model: car?.car_model ?? "",
    nickname: car?.nickname ?? "",
    year: car?.year ?? thisYear,
    mileage_km: car?.mileage_km ?? "",
    transmission: car?.transmission ?? "manual",
    fuel_type: car?.fuel_type ?? "petrol",
  });
  const [errors, setErrors] = useState({});
  // NOTE: fetches every model just to find one. Prefer a detail endpoint or exposing car_make on the car serializer.
  const editModelQuery = useQuery({
    queryKey: ["car-model", car?.car_model],
    queryFn: async () => (await getAll("/garage/models/")).find((model) => model.id === car.car_model),
    enabled: Boolean(car),
  });
  const selectedMake = make || (editModelQuery.data ? String(editModelQuery.data.car_make) : "");
  const modelQuery = useQuery({
    queryKey: ["car-models", selectedMake],
    queryFn: () => getAll(`/garage/models/?make=${encodeURIComponent(selectedMake)}`),
    enabled: Boolean(selectedMake),
  });
  const saveMutation = useMutation({
    mutationFn: (payload) =>
      api(car ? `/garage/cars/${car.id}/` : "/garage/cars/", { method: car ? "PATCH" : "POST", body: payload }),
    onSuccess: (...args) => {
      // Invalidate here so every caller (Garage, diagnosis flow, ...) sees the new car list.
      queryClient.invalidateQueries({ queryKey: carsKey });
      onSaved?.(...args);
    },
    onError: (error) => setErrors(parseErrors(error)),
  });
  const update = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
  function changeMake(event) {
    setMake(event.target.value);
    setForm((current) => ({ ...current, car_model: "" }));
    setErrors({});
  }
  function submit(event) {
    event.preventDefault();
    setErrors({});
    saveMutation.mutate({
      ...form,
      car_model: Number(form.car_model),
      year: Number(form.year),
      mileage_km: form.mileage_km === "" ? 0 : Number(form.mileage_km),
    });
  }

  return (
    <form className="panel stack" onSubmit={submit}>
      <h2>{car ? t("garage_edit") : t("garage_add")}</h2>
      <Field label={t("car_make")}>
        <select value={selectedMake} onChange={changeMake} required aria-invalid={Boolean(errors.car_model)}>
          <option value="">{t("car_choose_make")}</option>
          {(makeQuery.data || []).map((item) => (
            <option key={item.id} value={item.id}>{item.name}</option>
          ))}
        </select>
      </Field>
      <Field label={t("car_model")}>
        <select
          value={form.car_model}
          onChange={update("car_model")}
          required
          disabled={!selectedMake || modelQuery.isLoading}
          aria-invalid={Boolean(errors.car_model)}
        >
          <option value="">
            {!selectedMake ? t("car_choose_make_first") : modelQuery.isLoading ? t("loading") : t("car_choose_model")}
          </option>
          {(modelQuery.data || []).map((item) => (
            <option key={item.id} value={item.id}>
              {item.name} {item.generation} ({item.year_from}–{item.year_to || t("present")}, {item.engine_cc || "?"}cc)
            </option>
          ))}
        </select>
      </Field>
      <FieldError message={errors.car_model} />
      {editModelQuery.isError && <ErrorBox>{editModelQuery.error.message}</ErrorBox>}
      {modelQuery.isError && <ErrorBox>{modelQuery.error.message}</ErrorBox>}
      <div className="grid2">
        <div>
          <Field label={t("car_year")}>
            <input type="number" min="1980" max={thisYear + 1} value={numberInputValue(form.year)} onChange={update("year")} required aria-invalid={Boolean(errors.year)} />
          </Field>
          <FieldError message={errors.year} />
        </div>
        <div>
          <Field label={t("car_mileage")}>
            <input type="number" min="0" inputMode="numeric" value={numberInputValue(form.mileage_km)} onChange={update("mileage_km")} aria-invalid={Boolean(errors.mileage_km)} />
          </Field>
          <FieldError message={errors.mileage_km} />
        </div>
        <Field label={t("car_transmission")}>
          <select value={form.transmission} onChange={update("transmission")}>
            {TRANSMISSIONS.map((value) => (
              <option key={value} value={value}>{t(`trans_${value}`)}</option>
            ))}
          </select>
        </Field>
        <Field label={t("car_fuel")}>
          <select value={form.fuel_type} onChange={update("fuel_type")}>
            {FUELS.map((value) => (
              <option key={value} value={value}>{t(`fuel_${value}`)}</option>
            ))}
          </select>
        </Field>
      </div>
      <div>
        <Field label={t("car_nickname")} hint={t("optional")}>
          <input value={form.nickname} onChange={update("nickname")} maxLength={100} aria-invalid={Boolean(errors.nickname)} />
        </Field>
        <FieldError message={errors.nickname} />
      </div>
      <ErrorBox>{errors.form || errors.detail || (makeQuery.isError && makeQuery.error.message)}</ErrorBox>
      <div className="row">
        <button className="btn" disabled={saveMutation.isPending || makeQuery.isLoading}>
          {saveMutation.isPending ? t("saving") : t("car_save")}
        </button>
        <button type="button" className="btn ghost" onClick={onCancel}>{t("cancel")}</button>
      </div>
    </form>
  );
}

/* ------------------------------------------------------------------ */
/* Service history                                                     */
/* ------------------------------------------------------------------ */
function ServiceForm({ car, onCancel, onSaved }) {
  const { t } = useAuth();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    service_type: "",
    service_date: today(),
    cost: "",
    mileage_km: car.mileage_km ?? "", // sensible default: the car's current mileage
  });
  const [errors, setErrors] = useState({});
  const save = useMutation({
    mutationFn: () =>
      api("/garage/service-logs/", {
        method: "POST",
        body: {
          car: car.id,
          service_type: form.service_type.trim(),
          service_date: form.service_date,
          cost: form.cost === "" ? null : Number(form.cost),
          mileage_km: form.mileage_km === "" ? null : Number(form.mileage_km),
        },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: serviceLogsKey(car.id) });
      onSaved(); // closes the form
    },
    onError: (err) => setErrors(parseErrors(err)),
  });
  const update = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
  const listId = `service-types-${car.id}`;

  return (
    <form
      className="service-form stack"
      onSubmit={(event) => {
        event.preventDefault();
        setErrors({});
        save.mutate();
      }}
      onKeyDown={(event) => event.key === "Escape" && !save.isPending && onCancel()}
    >
      <h4>{t("garage_add_service")}</h4>
      <div className="grid2">
        <div>
          <Field label={t("garage_service")}>
            <input list={listId} value={form.service_type} onChange={update("service_type")} maxLength={100} required autoFocus aria-invalid={Boolean(errors.service_type)} />
          </Field>
          <datalist id={listId}>
            {SERVICE_SUGGESTIONS.map((name) => <option key={name} value={name} />)}
          </datalist>
          <FieldError message={errors.service_type} />
        </div>
        <div>
          <Field label={t("garage_service_date")}>
            <input type="date" max={today()} value={form.service_date} onChange={update("service_date")} required aria-invalid={Boolean(errors.service_date)} />
          </Field>
          <FieldError message={errors.service_date} />
        </div>
        <div>
          <Field label={t("car_mileage")}>
            <input type="number" min="0" inputMode="numeric" value={numberInputValue(form.mileage_km)} onChange={update("mileage_km")} aria-invalid={Boolean(errors.mileage_km)} />
          </Field>
          <FieldError message={errors.mileage_km} />
        </div>
        <div>
          <Field label={t("garage_service_cost")}>
            <input type="number" min="0" inputMode="numeric" value={numberInputValue(form.cost)} onChange={update("cost")} aria-invalid={Boolean(errors.cost)} />
          </Field>
          <FieldError message={errors.cost} />
        </div>
      </div>
      <ErrorBox>{errors.form || errors.detail || errors.car}</ErrorBox>
      <div className="row">
        <button className="btn" disabled={save.isPending}>{save.isPending ? t("saving") : t("car_save")}</button>
        <button type="button" className="btn ghost" onClick={onCancel} disabled={save.isPending}>{t("cancel")}</button>
      </div>
    </form>
  );
}

function ServiceRecordsDialog({ car, logs, onClose }) {
  const { t } = useAuth();
  const tr = useTr();
  const hasCost = logs.some((entry) => entry.cost != null);
  const total = logs.reduce((sum, entry) => sum + (entry.cost != null ? Number(entry.cost) || 0 : 0), 0);
  const titleId = `records-title-${car.id}`;
 
  // Escape closes; background page does not scroll while the dialog is open.
  useEffect(() => {
    const onKey = (event) => event.key === "Escape" && onClose();
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [onClose]);
 
  return (
    <div
      className="records-backdrop"
      role="presentation"
      onClick={(event) => event.target === event.currentTarget && onClose()}
    >
      <section className="records-dialog panel" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="section-head">
          <div>
            <h2 id={titleId}>{tr("service_records_title", "Service records")}</h2>
            <p className="muted small">
              {car.nickname || car.car_model_label} · {logs.length} {tr("service_records_count", "records")}
            </p>
          </div>
          <button type="button" className="btn ghost" autoFocus aria-label={tr("close", "Close")} onClick={onClose}>
            ✕
          </button>
        </div>
 
        {logs.length === 0 ? (
          <p className="muted">{t("garage_no_services")}</p>
        ) : (
          <div className="table-wrap">
            <table className="records-table">
              <thead>
                <tr>
                  <th scope="col">{t("garage_service_date")}</th>
                  <th scope="col">{t("garage_service")}</th>
                  <th scope="col" className="num">{t("car_mileage")}</th>
                  <th scope="col" className="num">{t("garage_service_cost")}</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((entry) => (
                  <tr key={entry.id}>
                    <td>{formatDate(entry.service_date)}</td>
                    <td>{entry.service_type}</td>
                    <td className="num">
                      {entry.mileage_km != null ? `${Number(entry.mileage_km).toLocaleString()} ${t("km")}` : "—"}
                    </td>
                    <td className="num">{entry.cost != null ? pkr(entry.cost) : "—"}</td>
                  </tr>
                ))}
              </tbody>
              {hasCost && (
                <tfoot>
                  <tr>
                    <td colSpan={3}>{tr("service_total", "Total spent")}</td>
                    <td className="num">{pkr(total)}</td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function ServiceHistory({ car, logsQuery, logs }) {
  const { t } = useAuth();
  const tr = useTr();
  const [adding, setAdding] = useState(false);
  const [viewing, setViewing] = useState(false);
  const headingId = `service-heading-${car.id}`;
 
  return (
    <section className="service-history" aria-labelledby={headingId}>
      <div className="section-head">
        <h3 id={headingId}>{t("garage_service_history")}</h3>
        {!adding && (
          <button type="button" className="btn ghost" onClick={() => setAdding(true)}>
            + {t("garage_add_service")}
          </button>
        )}
      </div>
 
      {adding && <ServiceForm car={car} onCancel={() => setAdding(false)} onSaved={() => setAdding(false)} />}
 
      {logsQuery.isLoading && <Spinner />}
      {logsQuery.isError && (
        <>
          <ErrorBox>{logsQuery.error.message}</ErrorBox>
          <button type="button" className="btn ghost" onClick={() => logsQuery.refetch()}>{t("retry")}</button>
        </>
      )}
      {logsQuery.isSuccess && logs.length === 0 && !adding && <p className="muted small">{t("garage_no_services")}</p>}
 
      {logs.length > 0 && (
        <div className="service-summary">
          <span className="muted small">
            {logs.length} {tr("service_records_count", "records")}
          </span>
          <button type="button" className="link-btn" onClick={() => setViewing(true)}>
            {tr("service_view_records", "View service records")} →
          </button>
        </div>
      )}
 
      {viewing && <ServiceRecordsDialog car={car} logs={logs} onClose={() => setViewing(false)} />}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Car card                                                            */
/* ------------------------------------------------------------------ */
function CarCard({ car, onEdit, onDelete }) {
  const { t } = useAuth();
  const tr = useTr();
  // One request per car (N+1). Fine for a handful of cars; batch server-side if garages grow.
  const logsQuery = useQuery({
    queryKey: serviceLogsKey(car.id),
    queryFn: () => getAll(`/garage/service-logs/?car=${car.id}`),
  });
  // Newest first, regardless of server ordering.
  const logs = useMemo(
    () =>
      [...(logsQuery.data ?? [])].sort(
        (a, b) => String(b.service_date).localeCompare(String(a.service_date)) || b.id - a.id
      ),
    [logsQuery.data]
  );
  const last = logs[0];

  return (
    <article className="panel car-card">
      <h2>{car.nickname || car.car_model_label}</h2>
      {car.nickname && <p className="muted">{car.car_model_label}</p>}
      <p className="muted small">
        {car.year} · {Number(car.mileage_km).toLocaleString()} {t("km")} · {t(`trans_${car.transmission}`)} · {t(`fuel_${car.fuel_type}`)}
      </p>
      {last && (
        <p className="muted small">
          {tr("garage_last_service", "Last service")}: {last.service_type}, {formatDate(last.service_date)}
        </p>
      )}
      <div className="row">
        <Link className="btn" to={`/diagnose?car=${car.id}`}>{t("garage_diagnose")}</Link>
        <button type="button" className="btn ghost" onClick={onEdit}>{t("garage_edit")}</button>
        <button type="button" className="link-btn danger" onClick={onDelete}>{t("garage_delete")}</button>
      </div>
      <ServiceHistory car={car} logsQuery={logsQuery} logs={logs} />
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */
export default function Garage() {
  const { t } = useAuth();
  const queryClient = useQueryClient();
  const cars = useCars();
  const [editing, setEditing] = useState(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");
  const [pendingDelete, setPendingDelete] = useState(null);

  const removeMutation = useMutation({
    mutationFn: (id) => api(`/garage/cars/${id}/`, { method: "DELETE" }),
    onSuccess: (_data, id) => {
      setPendingDelete(null);
      queryClient.removeQueries({ queryKey: serviceLogsKey(id) });
      queryClient.invalidateQueries({ queryKey: carsKey });
      queryClient.invalidateQueries({ queryKey: sessionsKey }); // History shows "car removed"
    },
    onError: (err) => setError(err.message),
  });

  const saved = () => {
    setAdding(false);
    setEditing(null);
  };
  const closeDelete = () => {
    setPendingDelete(null);
    setError("");
  };

  // Escape closes the delete dialog (unless a delete is in flight).
  useEffect(() => {
    if (!pendingDelete) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape" && !removeMutation.isPending) {
        setPendingDelete(null);
        setError("");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pendingDelete, removeMutation.isPending]);

  const list = cars.data ?? [];
  const canAdd = cars.isSuccess && list.length > 0 && !adding && !editing;

  return (
    <>
      <div className="section-head">
        <h1>{t("garage_title")}</h1>
        {canAdd && (
          <button type="button" className="btn" onClick={() => setAdding(true)}>+ {t("garage_add")}</button>
        )}
      </div>

      {cars.isLoading && <Spinner />}
      <ErrorBox>{cars.error?.message || (!pendingDelete && error)}</ErrorBox>
      {cars.isError && <button type="button" className="btn ghost" onClick={() => cars.refetch()}>{t("retry")}</button>}

      {/* New-car form sits at the top so it is visible without scrolling past every car. */}
      {adding && <AddCar onCancel={() => setAdding(false)} onSaved={saved} />}

      {cars.isSuccess && list.length === 0 && !adding && (
        <Empty action={<button type="button" className="btn" onClick={() => setAdding(true)}>{t("garage_add_first")}</button>}>
          <strong>{t("garage_empty_title")}</strong>
          <br />
          {t("garage_empty_body")}
        </Empty>
      )}

      {list.map((item) =>
        editing?.id === item.id ? (
          <AddCar key={item.id} car={editing} onCancel={() => setEditing(null)} onSaved={saved} />
        ) : (
          <CarCard
            key={item.id}
            car={item}
            onEdit={() => {
              setAdding(false);
              setEditing(item);
            }}
            onDelete={() => {
              setError("");
              setPendingDelete(item);
            }}
          />
        )
      )}

      {pendingDelete && (
        <div
          className="confirm-backdrop"
          role="presentation"
          onClick={(event) => event.target === event.currentTarget && !removeMutation.isPending && closeDelete()}
        >
          <section className="confirm-dialog panel" role="dialog" aria-modal="true" aria-labelledby="delete-title">
            <h2 id="delete-title">{t("garage_delete_title")}</h2>
            <p>{t("garage_delete_confirm", { car: pendingDelete.nickname || pendingDelete.car_model_label })}</p>
            <ErrorBox>{error}</ErrorBox>
            <div className="row">
              <button
                type="button"
                className="btn danger-button"
                disabled={removeMutation.isPending}
                onClick={() => removeMutation.mutate(pendingDelete.id)}
              >
                {removeMutation.isPending ? t("deleting") : t("garage_delete")}
              </button>
              {/* Safer default focus for a destructive dialog */}
              <button type="button" className="btn ghost" autoFocus disabled={removeMutation.isPending} onClick={closeDelete}>
                {t("cancel")}
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  );
}