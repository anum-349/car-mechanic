const CACHE_PREFIX = "garidoc-offline:";

export function readOfflineCache(key) {
  try {
    const raw = window.localStorage.getItem(`${CACHE_PREFIX}${key}`);
    return raw ? JSON.parse(raw) : undefined;
  } catch {
    return undefined;
  }
}

export function writeOfflineCache(key, data) {
  try {
    window.localStorage.setItem(`${CACHE_PREFIX}${key}`, JSON.stringify(data));
  } catch {
    // The live API remains usable when storage is unavailable or full.
  }
}
