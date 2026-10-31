import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../src/auth.jsx";
import NewDiagnosis from "../src/pages/NewDiagnosis.jsx";
import DiagnosisChat from "../src/pages/DiagnosisChat.jsx";

vi.mock("../src/api.js", () => ({
  api: vi.fn(),
  getAll: vi.fn(),
  getStoredUser: () => null,
  getToken: () => null,
  setStoredUser: () => {},
  setToken: () => {},
  setRefresh: () => {},
}));

import { api, getAll } from "../src/api.js";

function renderStart(path = "/diagnose") {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <AuthProvider><MemoryRouter initialEntries={[path]}><Routes>
      <Route path="/diagnose" element={<NewDiagnosis />} />
      <Route path="/diagnose/:id" element={<DiagnosisChat />} />
    </Routes></MemoryRouter></AuthProvider>
  </QueryClientProvider>);
}

describe("diagnosis start", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
    getAll.mockResolvedValue([
      { id: 3, nickname: "My car", car_model_label: "Suzuki Alto", year: 2020 },
    ]);
  });

  it("requires a description and starts text diagnosis without a category", async () => {
    api.mockImplementation((path) => Promise.resolve(path === "/sessions/"
      ? { id: 12 }
      : { id: 12, status: "in_progress", answers: [], question: {
        id: 8, text: "What happens?", options: [{ id: 9, label: "Not sure", is_unsure: true }],
      } }));
    const user = userEvent.setup();
    renderStart();
    await user.click(await screen.findByRole("button", { name: "No, none of these" }));
    await user.click(screen.getByRole("radio", { name: /My car/ }));
    const description = screen.getByLabelText("Describe the problem in your own words");
    const start = screen.getByRole("button", { name: "Start diagnosis" });
    expect(description).toBeRequired();
    expect(start).toBeDisabled();
    await user.type(description, "It cranks slowly");
    await user.click(start);
    expect(await screen.findByRole("heading", { name: "What happens?" })).toBeInTheDocument();
    expect(api).toHaveBeenCalledWith("/sessions/", {
      method: "POST", body: { car: 3, free_text: "It cranks slowly" },
    });
    expect(api).not.toHaveBeenCalledWith(expect.stringContaining("/free-text/"), expect.anything());
  });

  it("hides free text and sends only the selected OBD code", async () => {
    api.mockImplementation((path) => Promise.resolve(path === "/obd/P0301/"
      ? { code: "P0301", description: "Cylinder 1 misfire", system: "Engine" }
      : path === "/sessions/" ? { id: 15 } : {
        id: 15, diagnosis_type: "obd", obd_context: {
          code: "P0301", description: "Cylinder 1 misfire", system: "Engine",
        }, answers: [], question: {
          id: 24, text: "Does the engine shake?", options: [
            { id: 25, label: "Yes", is_unsure: false },
            { id: 26, label: "Not sure", is_unsure: true },
          ],
        },
      }));
    const user = userEvent.setup();
    renderStart("/diagnose?obd=P0301");
    await user.click(await screen.findByRole("button", { name: "No, none of these" }));
    await user.click(screen.getByRole("radio", { name: /My car/ }));
    expect(screen.queryByLabelText("Describe the problem in your own words")).not.toBeInTheDocument();
    expect(screen.getByText("Cylinder 1 misfire")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Start diagnosis" }));
    expect(await screen.findByRole("heading", { name: "Does the engine shake?" })).toBeInTheDocument();
    expect(api).toHaveBeenCalledWith("/sessions/", {
      method: "POST", body: { car: 3, obd_code: "P0301" },
    });
  });
});
