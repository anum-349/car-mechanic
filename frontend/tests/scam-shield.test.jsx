import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../src/auth.jsx";
import ScamShield from "../src/pages/ScamShield.jsx";

vi.mock("../src/api.js", () => ({
  api: vi.fn(),
  trackEvent: vi.fn(() => Promise.resolve()),
  getAll: vi.fn(),
  getStoredUser: () => null,
  getToken: () => null,
  setStoredUser: () => {},
  setToken: () => {},
  setRefresh: () => {},
}));

import { api, getAll } from "../src/api.js";

const session = { id: 4, status: "completed", started_at: "2026-01-15T10:00:00Z" };
const cause = { id: 7, name: "Weak battery" };

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><AuthProvider><MemoryRouter><ScamShield /></MemoryRouter></AuthProvider></QueryClientProvider>);
}

describe("Scam Shield quote form", () => {
  beforeEach(() => {
    localStorage.clear();
    api.mockReset();
    getAll.mockImplementation((path) => Promise.resolve(path === "/sessions/" ? [session] : [cause]));
    api.mockImplementation((path) => Promise.resolve(path.includes("/result/") ? { results: [cause] } : null));
  });

  it("posts a selected diagnosis and displays text, colour, and icon with proof requests", async () => {
    const user = userEvent.setup();
    const recommendedSolution = {
      cause: 8,
      cause_name: "Alternator fault",
      confidence: "0.8",
      band: "very likely",
      cost: {
        city: "Lahore",
        parts_min: 18000,
        parts_max: 30000,
        labour_min: 3000,
        labour_max: 5000,
        total_min: 21000,
        total_max: 35000,
      },
      ask_your_mechanic: "Could you show me the alternator test results?",
    };
    api.mockImplementation((path, options) => {
      if (path.includes("/result/")) return Promise.resolve({ results: [recommendedSolution] });
      if (options?.method === "POST") return Promise.resolve({
        id: 31,
        verdict: "doubtful",
        claimed_cause: cause.id,
        limited: false,
        candidate_causes: [{ id: cause.id, name: cause.name, confidence: "0.7" }],
        cost: { city: "Lahore", total_min: 9000, total_max: 18500 },
        price_basis: "local_city",
        reasons: ["The quote is higher than the usual range."],
        proof_suggestions: ["Ask which part is worn and ask to be shown it."],
      });
      return Promise.resolve(null);
    });
    renderScreen();
    await user.selectOptions(await screen.findByLabelText("Choose a completed diagnosis"), "4");
    await user.selectOptions(screen.getByLabelText("Which cause did the mechanic name?"), "7");
    await user.type(screen.getByLabelText("What did the mechanic say needs repair?"), "Battery replacement");
    await user.type(screen.getByLabelText("Quoted price (PKR)"), "30000");
    await user.click(screen.getByRole("button", { name: "Compare this quote" }));
    expect(await screen.findByText("Worth checking further")).toBeInTheDocument();
    expect(screen.getByText("The quote is higher than the usual range.")).toBeInTheDocument();
    expect(screen.getByText("Ask which part is worn and ask to be shown it.")).toBeInTheDocument();
    expect(screen.getByText("Top solution suggested by your diagnosis")).toBeInTheDocument();
    expect(screen.getByText("Alternator fault")).toBeInTheDocument();
    expect(screen.getByText("The mechanic's selected cause differs from the top cause suggested by your symptom check. Ask for the tests that support each diagnosis before approving a repair.")).toBeInTheDocument();
    expect(screen.getByText("Could you show me the alternator test results?")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Estimated repair costs" })).toBeInTheDocument();
    expect(screen.getByText("?")).toBeInTheDocument();
    expect(api).toHaveBeenCalledWith("/scam-check/", {
      method: "POST",
      body: { session: 4, claimed_cause: 7, claim_text: "Battery replacement", quoted_price: 30000 },
    });
  });

  it("shows the limited response and lets the user select a listed candidate", async () => {
    const user = userEvent.setup();
    api.mockImplementation((path, options) => {
      if (path.includes("/result/")) return Promise.resolve({ results: [cause] });
      if (options?.method === "POST") return Promise.resolve({
        id: 32, verdict: "doubtful", limited: true, claimed_cause: null,
        candidate_causes: [{ id: cause.id, name: cause.name, confidence: "0.7" }],
        reasons: ["Choose a cause from the diagnosis results."],
        proof_suggestions: ["Ask for the old part back."], cost: {}, price_basis: "unavailable",
      });
      return Promise.resolve(null);
    });
    renderScreen();
    await user.selectOptions(await screen.findByLabelText("Choose a completed diagnosis"), "4");
    await user.type(screen.getByLabelText("What did the mechanic say needs repair?"), "Engine issue");
    await user.type(screen.getByLabelText("Quoted price (PKR)"), "12000");
    await user.click(screen.getByRole("button", { name: "Compare this quote" }));
    expect(await screen.findByText("Choose one of the listed causes, then compare the quote again.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Weak battery" }));
    await waitFor(() => expect(screen.queryByText("Choose one of the listed causes, then compare the quote again.")).not.toBeInTheDocument());
    expect(screen.getByLabelText("Which cause did the mechanic name?")).toHaveValue("7");
  });
});
