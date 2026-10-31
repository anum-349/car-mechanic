import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../src/auth.jsx";
import Mechanics from "../src/pages/Mechanics.jsx";

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

const mechanic = {
  user: 8,
  workshop_name: "Northside Auto",
  address: "12 Main Road",
  city: "Lahore",
  phone: "+923001234567",
  specialization: "Electrical",
  experience_years: 12,
  is_verified: true,
  average_rating: 4.5,
  review_count: 4,
};
const reviews = [1, 2, 3, 4].map((id) => ({
  id,
  reviewer_name: `Driver ${id}`,
  rating: id === 4 ? 3 : 5,
  work_quality: 5,
  price_fairness: 4,
  communication: 5,
  timeliness: 4,
  comment: `Review ${id}`,
  status: "approved",
  created_at: `2026-01-0${id}T10:00:00Z`,
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AuthProvider><MemoryRouter><Mechanics /></MemoryRouter></AuthProvider>
    </QueryClientProvider>,
  );
}

describe("mechanic directory", () => {
  beforeEach(() => {
    localStorage.clear();
    api.mockReset();
    getAll.mockImplementation((path) => api(path).then((response) => response.results || response));
    api.mockImplementation((path, options) => {
      if (path.startsWith("/accounts/mechanics/")) return Promise.resolve({ results: [mechanic] });
      if (path.startsWith("/reviews/") && options?.method === "POST") {
        return Promise.resolve({ status: "pending" });
      }
      if (path.startsWith("/reviews/")) return Promise.resolve({ results: reviews, next: null });
      return Promise.resolve(null);
    });
  });

  it("shows the latest three reviews and expands to contact details and all reviews", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("Review 1")).toBeInTheDocument();
    expect(screen.getByText("Review 2")).toBeInTheDocument();
    expect(screen.getByText("Review 3")).toBeInTheDocument();
    expect(screen.queryByText("Review 4")).not.toBeInTheDocument();
    expect(screen.queryByText("12 Main Road")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Read more: shop details and reviews" }));
    expect(screen.getByText("12 Main Road")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "+923001234567" })).toHaveAttribute("href", "tel:+923001234567");
    expect(screen.getByText("Review 4")).toBeInTheDocument();
    expect(screen.getAllByText("Work quality: 5/5")).toHaveLength(4);
    expect(screen.getByLabelText("Work quality")).toBeInTheDocument();
  });

  it("submits criterion ratings for a mechanic review", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Read more: shop details and reviews" }));

    for (const [label, value] of [
      ["Work quality", "5"],
      ["Price fairness", "4"],
      ["Communication and explanation", "3"],
      ["Timeliness", "2"],
    ]) {
      await user.selectOptions(screen.getByLabelText(label), value);
    }
    await user.type(screen.getByLabelText("Optional comment"), "Work was completed as agreed.");
    await user.click(screen.getByRole("button", { name: "Submit review" }));

    expect(await screen.findByText("Thanks. Your review will show to everyone after a quick check.")).toBeInTheDocument();
    expect(api).toHaveBeenCalledWith("/reviews/", {
      method: "POST",
      body: {
        mechanic: mechanic.user,
        work_quality: 5,
        price_fairness: 4,
        communication: 3,
        timeliness: 2,
        comment: "Work was completed as agreed.",
      },
    });
  });
});
