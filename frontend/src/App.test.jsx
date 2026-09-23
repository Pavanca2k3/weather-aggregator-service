import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const reading = {
  id: 1,
  city: "Bengaluru",
  temperature_c: 21.4,
  windspeed_kmh: 7.2,
  weathercode: 2,
  description: "Partly cloudy",
  is_day: 1,
  observed_at: "2024-05-01T10:00:00Z",
  fetched_at: "2024-05-01T10:00:05Z",
};

function jsonResponse(body, status = 200) {
  return { ok: status < 400, status, json: async () => body };
}

beforeEach(() => {
  global.fetch = vi.fn();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("App", () => {
  it("renders the city input and the fetch button", () => {
    render(<App />);

    expect(screen.getByLabelText("City")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fetch & store" })).toBeInTheDocument();
  });

  it("posts the city, reloads the history and renders the reading", async () => {
    const user = userEvent.setup();
    // run() fires the action first, then always re-reads the history
    global.fetch
      .mockResolvedValueOnce(jsonResponse(reading))
      .mockResolvedValueOnce(jsonResponse([reading]));

    render(<App />);
    await user.type(screen.getByLabelText("City"), "bengaluru");
    await user.click(screen.getByRole("button", { name: "Fetch & store" }));

    expect(await screen.findByRole("heading", { name: "Bengaluru" })).toBeInTheDocument();
    // each value shows twice: once in the latest panel, once in the single history row
    expect(screen.getAllByText("21.4°C")).toHaveLength(2);
    expect(screen.getAllByText(/Partly cloudy/)).toHaveLength(2);
    expect(screen.getByText(/1 reading stored/)).toBeInTheDocument();

    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(global.fetch.mock.calls[0]).toEqual([
      "/api/weather/fetch?city=bengaluru",
      { method: "POST" },
    ]);
    expect(global.fetch.mock.calls[1][0]).toBe("/api/weather/bengaluru");
  });

  it("renders the API error detail when the city cannot be resolved", async () => {
    const user = userEvent.setup();
    global.fetch.mockResolvedValueOnce(
      jsonResponse({ detail: "Could not resolve city: 'Atlantis'" }, 404),
    );

    render(<App />);
    await user.type(screen.getByLabelText("City"), "Atlantis");
    await user.click(screen.getByRole("button", { name: "Fetch & store" }));

    expect(await screen.findByText("Could not resolve city: 'Atlantis'")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    // the history read is skipped once the fetch fails
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it("only reads the stored history when History is clicked", async () => {
    const user = userEvent.setup();
    global.fetch.mockResolvedValueOnce(jsonResponse([reading]));

    render(<App />);
    await user.type(screen.getByLabelText("City"), "Bengaluru");
    await user.click(screen.getByRole("button", { name: "History" }));

    expect(await screen.findByRole("table")).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch.mock.calls[0][0]).toBe("/api/weather/Bengaluru");
  });
});
