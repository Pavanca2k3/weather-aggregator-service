// The API supplies the human-readable weather description (WMO 4677), so the
// UI does not keep its own copy of that table -- one source of truth, no drift.

export function formatTime(iso) {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
