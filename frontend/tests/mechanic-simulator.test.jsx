import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../src/auth.jsx";
import MechanicSimulator from "../src/pages/mechanic/MechanicSimulator.jsx";

vi.mock("../src/api.js", () => ({
  api: vi.fn(),
  getAll: vi.fn(async (path) => {
    if (path.includes("models")) return [{ id: 1, car_make: 10, name: "Hatch", generation: "A" }];
    if (path.includes("makes")) return [{ id: 10, name: "TestMake" }];
    return [{ id: 20, name_en: "Starting problem" }];
  }),
  getStoredUser: () => null, getToken: () => null, setStoredUser: () => {},
  setToken: () => {}, setRefresh: () => {},
}));

import { api } from "../src/api.js";

function renderSimulator() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><AuthProvider><MechanicSimulator /></AuthProvider></MemoryRouter>
  </QueryClientProvider>);
}

describe("mechanic simulator", () => {
  beforeEach(() => api.mockReset());

  it("uses the shared QuestionCard and shows ranked causes after an answer", async () => {
    api.mockResolvedValueOnce({ simulated: true, ranked_causes: [], evidence: { present: [] },
      next_question: { id: 30, text: "Does it crank slowly?", options: [
        { id: 40, label: "Yes", is_unsure: false }, { id: 41, label: "Not sure", is_unsure: true },
      ] }, editable_symptoms: [] });
    api.mockResolvedValueOnce({ simulated: true, ranked_causes: [{
      cause: { id: 50, name: "Weak battery", status: "ai_draft", created_by: null }, rank: 1,
      explanation: "Supported by yes", supporting_symptoms: [{ symptom: "Slow crank" }],
      contradicting_symptoms: [], contributing_links: [], all_links: [],
    }], evidence: { present: [{ id: 60, symptom: "Slow crank" }] }, next_question: null,
    editable_symptoms: [{ id: 60, text: "Slow crank" }] });
    renderSimulator();
    await screen.findByRole("heading", { name: "Test a guidance flow" });
    fireEvent.change(screen.getByLabelText("Car model"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Problem"), { target: { value: "20" } });
    fireEvent.click(screen.getByRole("button", { name: "Start test drive-through" }));
    expect(await screen.findByText("Does it crank slowly?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Yes" }));
    expect(await screen.findByRole("heading", { name: "Weak battery" })).toBeInTheDocument();
    expect(screen.getByText("Supported by yes")).toBeInTheDocument();
    await waitFor(() => expect(api).toHaveBeenCalledTimes(2));
  });
});
