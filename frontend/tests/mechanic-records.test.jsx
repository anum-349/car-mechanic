import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../src/auth.jsx";
import MechanicRecords from "../src/pages/mechanic/MechanicRecords.jsx";

vi.mock("../src/api.js", () => ({
  api: vi.fn(),
  getAll: vi.fn(),
  getRefresh: () => null,
  getStoredUser: () => ({ id: 44, role: "mechanic", language: "en" }),
  getToken: () => null,
  setStoredUser: () => {},
  setToken: () => {},
  setRefresh: () => {},
}));

import { api } from "../src/api.js";

const vehicle = {
  id: 3,
  label: "Daily car",
  model: "Test make Test model",
  year: 2021,
  mileage_km: 45000,
};

const record = {
  id: 11,
  status: "in_progress",
  diagnosis_type: "text",
  free_text: "The engine cranks slowly.",
  car: vehicle,
  category_label: "Starting",
  obd_code: null,
  obd_context: null,
  safety_alert: false,
  started_at: "2026-01-01T10:00:00Z",
  completed_at: null,
  symptoms: [],
  answers: [],
  results: [],
  inspections: [],
  outcome: null,
  outcome_history: [],
};

function renderPage(path = "/mechanic/records/new") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/mechanic/records/:id" element={<MechanicRecords />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("mechanic diagnosis records", () => {
  beforeEach(() => {
    localStorage.clear();
    api.mockReset();
    api.mockImplementation((path, options) => {
      if (path === "/mechanic/records/vehicles/") return Promise.resolve([vehicle]);
      if (path === "/sessions/" && options?.method === "POST") {
        return Promise.resolve({ id: record.id });
      }
      if (path === `/mechanic/records/${record.id}/`) return Promise.resolve(record);
      return Promise.resolve(null);
    });
  });

  it("requires a problem description before registering a record", async () => {
    renderPage();
    await screen.findByLabelText("Vehicle");
    fireEvent.change(screen.getByLabelText("Vehicle"), { target: { value: "3" } });
    await userEvent.click(screen.getByRole("button", { name: "Start diagnosis" }));

    expect(screen.getByLabelText("Problem reported")).toBeRequired();
    expect(api).not.toHaveBeenCalledWith("/sessions/", expect.anything());
  });

  it("starts a real diagnosis session and opens its record", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.selectOptions(await screen.findByLabelText("Vehicle"), "3");
    await user.type(screen.getByLabelText("Problem reported"), "The engine cranks slowly.");
    await user.click(screen.getByRole("button", { name: "Start diagnosis" }));

    expect(await screen.findByText("AI diagnosis evidence")).toBeInTheDocument();
    expect(api).toHaveBeenCalledWith("/sessions/", {
      method: "POST",
      body: { car: 3, free_text: "The engine cranks slowly." },
    });
    expect(await screen.findByText("The engine cranks slowly.")).toBeInTheDocument();
  });
});
