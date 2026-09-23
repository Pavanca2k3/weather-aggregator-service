import { useState } from "react";
import { fetchWeather, getReadings } from "./api";
import { formatTime } from "./format";
import "./App.css";

export default function App() {
  const [city, setCity] = useState("");
  const [readings, setReadings] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(action) {
    const name = city.trim();
    if (!name) return;

    setBusy(true);
    setError("");
    try {
      await action(name);
      // always re-read the history so the table reflects what is stored,
      // not just what the last call happened to return
      setReadings(await getReadings(name));
    } catch (err) {
      setError(err.message);
      setReadings(null);
    } finally {
      setBusy(false);
    }
  }

  const latest = readings?.[0];

  return (
    <main>
      <h1>Weather Aggregator</h1>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          run(fetchWeather);
        }}
      >
        <input
          value={city}
          onChange={(e) => setCity(e.target.value)}
          placeholder="City, e.g. Bengaluru"
          aria-label="City"
          autoFocus
        />
        <button type="submit" disabled={busy || !city.trim()}>
          {busy ? "Working…" : "Fetch & store"}
        </button>
        <button
          type="button"
          onClick={() => run(async () => {})}
          disabled={busy || !city.trim()}
        >
          History
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {latest && (
        <section className="latest">
          <h2>{latest.city}</h2>
          <p className="temp">{latest.temperature_c.toFixed(1)}°C</p>
          <p className="desc">
            {latest.description} · wind {latest.windspeed_kmh.toFixed(1)} km/h ·{" "}
            {latest.is_day ? "day" : "night"}
          </p>
          <p className="observed">Observed {formatTime(latest.observed_at)}</p>
        </section>
      )}

      {readings && readings.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Observed</th>
              <th>Fetched</th>
              <th>Temp</th>
              <th>Wind</th>
              <th>Conditions</th>
            </tr>
          </thead>
          <tbody>
            {readings.map((r) => (
              <tr key={r.id}>
                <td>{formatTime(r.observed_at)}</td>
                <td>{formatTime(r.fetched_at)}</td>
                <td>{r.temperature_c.toFixed(1)}°C</td>
                <td>{r.windspeed_kmh.toFixed(1)} km/h</td>
                <td>{r.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {readings && (
        <p className="note">
          {readings.length} reading{readings.length === 1 ? "" : "s"} stored. Rows sharing an
          observation time are repeat polls of unchanged weather.
        </p>
      )}
    </main>
  );
}
