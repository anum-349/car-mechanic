import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../src/auth.jsx";
import { AddCar } from "../src/pages/Garage.jsx";

vi.mock("../src/api.js", () => ({
  api: vi.fn(),
  getAll: vi.fn(async (path) => path.includes("makes")
    ? [{ id: 4, name: "Suzuki" }]
    : [{ id: 12, car_make: 4, name: "Alto", generation: "HA", year_from: 2000, year_to: 2014, engine_cc: 660 }]),
  getStoredUser: () => null,
  getToken: () => null,
  setStoredUser: () => {},
  setToken: () => {},
  setRefresh: () => {},
}));

import { api } from "../src/api.js";

function renderForm(car) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AuthProvider><AddCar car={car} onCancel={() => {}} onSaved={() => {}} /></AuthProvider></QueryClientProvider>);
}

describe("AddCar validation", () => {
  beforeEach(() => { localStorage.clear(); api.mockReset(); });

  it("requires a make and model before submitting", async () => {
    const user = userEvent.setup();
    renderForm();
    await user.click(screen.getByRole("button", { name: "Save car" }));
    expect(screen.getByLabelText("Make")).toBeInvalid();
    expect(screen.getByLabelText("Model")).toBeDisabled();
    expect(api).not.toHaveBeenCalled();
  });

  it("blocks out-of-range year and negative mileage", async () => {
    const user = userEvent.setup();
    renderForm();
    await screen.findByRole("option", { name: "Suzuki" });
    await user.selectOptions(screen.getByLabelText("Make"), "4");
    await screen.findByRole("option", { name: /Alto/ });
    await user.selectOptions(await screen.findByLabelText("Model"), "12");
    fireEvent.change(screen.getByLabelText("Year"), { target: { value: "1970" } });
    fireEvent.change(screen.getByLabelText("Mileage (km)"), { target: { value: "-1" } });
    expect(screen.getByLabelText("Year")).toBeInvalid();
    expect(screen.getByLabelText("Mileage (km)")).toBeInvalid();
    await user.click(screen.getByRole("button", { name: "Save car" }));
    expect(api).not.toHaveBeenCalled();
  });

  it("does not pass a non-numeric saved year to the number input", async () => {
    renderForm({ id: 8, car_model: 12, year: "p0301", mileage_km: 1200 });
    await screen.findByRole("option", { name: /Alto/ });
    expect(screen.getByLabelText("Year")).toHaveValue(null);
    expect(screen.getByLabelText("Year")).toBeInvalid();
  });

  it("shows API validation messages beside the field", async () => {
    api.mockRejectedValueOnce({ data: { year: ["This year does not match the selected model."] }, message: "Invalid data" });
    const user = userEvent.setup();
    renderForm();
    await screen.findByRole("option", { name: "Suzuki" });
    await user.selectOptions(screen.getByLabelText("Make"), "4");
    await screen.findByRole("option", { name: /Alto/ });
    await user.selectOptions(await screen.findByLabelText("Model"), "12");
    await user.click(screen.getByRole("button", { name: "Save car" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This year does not match the selected model.");
    await waitFor(() => expect(api).toHaveBeenCalledWith("/garage/cars/", expect.objectContaining({ method: "POST" })));
  });
});
