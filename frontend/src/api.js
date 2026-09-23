// All calls go through Vite's /api proxy (see vite.config.js), so the browser
// never needs to know the backend's port and there is no CORS hop in dev.
const BASE = "/api";

async function request(path, options) {
  const response = await fetch(BASE + path, options);

  if (!response.ok) {
    // the API returns {"detail": "..."} for 404 and 502
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // non-JSON body; keep the generic message
    }
    throw new Error(detail);
  }

  if (response.status === 204) return null;
  return response.json();
}

export function fetchWeather(city) {
  return request(`/weather/fetch?city=${encodeURIComponent(city)}`, { method: "POST" });
}

export function getReadings(city) {
  return request(`/weather/${encodeURIComponent(city)}`);
}

export function getLatest(city) {
  return request(`/weather/${encodeURIComponent(city)}/latest`);
}
