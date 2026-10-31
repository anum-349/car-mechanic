/* eslint-disable react-refresh/only-export-components */
import { Children, cloneElement, useCallback, useEffect, useId, useState } from "react";
import { useAuth } from "../auth.jsx";

export function Spinner() {
  const { t } = useAuth() || { t: (k) => k };
  return (
    <p className="muted" role="status">
      {t("loading")}…
    </p>
  );
}

export function ErrorBox({ children }) {
  if (!children) return null;
  return (
    <p className="error" role="alert">
      {children}
    </p>
  );
}

export function Empty({ children, action }) {
  return (
    <div className="empty">
      <p>{children}</p>
      {action}
    </div>
  );
}

export function Field({ label, children, hint }) {
  // The label and the hint are separate: the hint is read as a description,
  // not as part of the field's name.
  const id = useId();
  const hintId = `${id}-hint`;
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      {(() => {
        const child = Children.only(children);
        if (child.type === "div" && child.props.className === "password-input") {
          const control = Children.map(child.props.children, (nested) => {
            if (nested.type === "input") {
              return cloneElement(nested, { id, "aria-describedby": hint ? hintId : undefined });
            }
            return nested;
          });
          return cloneElement(child, {}, control);
        }
        return cloneElement(child, { id, "aria-describedby": hint ? hintId : undefined });
      })()}
      {hint && (
        <span id={hintId} className="muted small">
          {hint}
        </span>
      )}
    </div>
  );
}

// Loads data when the page opens. reload() fetches again.
export function useLoad(fn, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const reload = useCallback(() => {
    setLoading(true);
    setError("");
    return fn()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  // This generic loader accepts call-site dependencies, so the array is intentionally dynamic.
  // eslint-disable-next-line react-hooks/use-memo
  }, deps);
  useEffect(() => {
    reload();
  }, [reload]);
  return { data, error, loading, reload, setData };
}

export const pkr = (n) => `PKR ${Number(n).toLocaleString("en-PK")}`;
export const formatDate = (iso) =>
  new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
