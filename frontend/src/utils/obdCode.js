export function normalizeObdCode(value) {
  const code = String(value ?? "").trim().toUpperCase();
  return /^[PBCU][0-9A-F]{4}$/.test(code) ? code : null;
}
