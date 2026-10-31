// src/helpers.js
// Small shared helpers used across pages.
import { useEffect } from "react";
import { useAuth } from "./auth.jsx";

// t() returns the key when a translation is missing; fall back to readable English instead.
export function useTr() {
  const { t } = useAuth();
  return (key, fallback) => {
    const v = t(key);
    return !v || v === key ? fallback : v;
  };
}

// Errors can be an Error, an ApiError carrying field errors in `.data`, or a plain string.
export function errMsg(err) {
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

// Dialog behaviour: Escape closes (unless `locked`, e.g. while sending) and the page behind doesn't scroll.
export function useModal(onClose, locked = false) {
  useEffect(() => {
    const onKey = (event) => event.key === "Escape" && !locked && onClose();
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [onClose, locked]);
}

/* ------------------------------------------------------------------ */
/* Symptom description checks                                          */
/* ------------------------------------------------------------------ */
export const DETAIL_MIN_WORDS = 3;
export const DETAIL_MIN_CHARS = 15;

// Cheap client-side sanity check, run BEFORE anything is sent. It catches empty, too-short and
// obviously junk input ("asdf", "aaaaaaa", "....."). It cannot judge relevance: text that is
// well-formed but unrelated to cars is rejected by the server (clarification_required / 400).
export function checkDetail(raw) {
  const text = String(raw ?? "").trim().replace(/\s+/g, " ");
  const words = text.split(" ").filter(Boolean);
  if (words.length < DETAIL_MIN_WORDS || text.length < DETAIL_MIN_CHARS) return { ok: false, code: "short" };
  const letters = (text.match(/\p{L}/gu) || []).length;
  const nonSpace = text.replace(/\s/g, "").length;
  if (letters / nonSpace < 0.6) return { ok: false, code: "junk" };
  if (/(.)\1{4,}/u.test(text)) return { ok: false, code: "junk" };
  if (new Set(words.map((word) => word.toLowerCase())).size < 2) return { ok: false, code: "junk" };
  return { ok: true, code: "ok" };
}

export function detailMessage(code, tr) {
  if (code === "junk") {
    return tr(
      "diagnosis_detail_err_junk",
      "That doesn't look like a description of a car problem. Tell us what you notice, hear, smell or see."
    );
  }
  return tr(
    "diagnosis_detail_err_short",
    "Please add a little more detail: at least 3 words, for example “engine shakes when I brake”."
  );
}