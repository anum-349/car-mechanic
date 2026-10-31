import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "../src/auth.jsx";
import { MemoryRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { api, getAll } from "../src/api.js";
import MechanicWizard from "../src/pages/mechanic/MechanicWizard.jsx";
import StrengthSelector from "../src/pages/mechanic/StrengthSelector.jsx";
import { readDraft, writeDraft } from "../src/pages/mechanic/wizardModel.js";

vi.mock("../src/api.js", () => ({
  api: vi.fn(), getAll: vi.fn(async () => []), getStoredUser: () => ({ id: 71, role: "mechanic" }),
  getToken: () => null, setStoredUser: () => {}, setToken: () => {}, setRefresh: () => {},
}));

const baseFlow = () => ({
  category: { name_en: "Engine", name_roman: "Engine" },
  car_models: ["Make Model"],
  symptoms: [
    { key: "slow_crank", en: "Slow crank", roman: "Self dheema", safety: false, safety_explanation: "" },
  ],
  causes: [],
  questions: [],
  self_checks: [],
  red_flags: [],
});

function renderWizard(step) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <MemoryRouter initialEntries={[`/mechanic/wizard?flow=1&step=${step}`]}>
          <MechanicWizard />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("mechanic wizard controls", () => {
  beforeEach(() => {
    localStorage.clear();
    api.mockReset();
    getAll.mockImplementation(async (path) => {
      if (path === "/garage/models/") return [{ id: 1, car_make: 1, name: "Model" }];
      if (path === "/garage/makes/") return [{ id: 1, name: "Make" }];
      if (path === "/categories/") return [{ id: 1, name_en: "Engine", name_roman: "Engine" }];
      return [];
    });
    api.mockImplementation(async (path) => {
      if (path === "/mechanic/flows/1/") return {
        id: 1,
        symptoms: [{ id: 11, key: "slow_crank" }],
        causes: [],
      };
      return { id: 1, symptoms: [], causes: [] };
    });
  });

  it("selects one named symptom strength without exposing a number", () => {
    const onChange = vi.fn();
    render(<AuthProvider><StrengthSelector name="Link strength" value="often" onChange={onChange} /></AuthProvider>);
    expect(screen.getByRole("button", { name: "Often" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Always" })).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(screen.getByRole("button", { name: "Rarely" }));
    expect(onChange).toHaveBeenCalledWith("rarely");
    expect(document.body.textContent).not.toMatch(/0\.9|0\.7|0\.4|0\.1/);
  });

  it("autosaves and restores the current flow and step", () => {
    const draft = { flowId: 4, step: 6, flow: { category: { name_en: "Engine" }, symptoms: [] } };
    expect(writeDraft(71, draft)).toBe(true);
    expect(readDraft(71)).toEqual(draft);
    expect(readDraft(72)).toBeNull();
  });

  it("removes an accidentally added symptom and deletes its saved server record", async () => {
    const user = userEvent.setup();
    writeDraft(71, { flowId: 1, step: 2, flow: baseFlow() });
    renderWizard(2);

    await user.click(await screen.findByRole("button", { name: "Add another symptom" }));
    expect(screen.getAllByLabelText("How would a customer describe it? (English)")).toHaveLength(2);
    await user.click(screen.getAllByRole("button", { name: "Remove symptom" })[1]);

    await waitFor(() => expect(readDraft(71).flow.symptoms).toHaveLength(1));
    expect(api).toHaveBeenCalledWith("/mechanic/flows/1/");
    expect(api).not.toHaveBeenCalledWith("/mechanic/items/symptoms/11/", { method: "DELETE" });
    expect(screen.getAllByLabelText("How would a customer describe it? (English)")).toHaveLength(1);
  });

  it("deletes a previously saved symptom when it is removed from the form", async () => {
    const user = userEvent.setup();
    const flow = baseFlow();
    flow.symptoms.push({
      key: "engine_noise",
      en: "Unusual engine noise",
      roman: "Engine ki ghair mamooli awaz",
      safety: false,
      safety_explanation: "",
    });
    writeDraft(71, { flowId: 1, step: 2, flow });
    api.mockImplementation(async (path) => {
      if (path === "/mechanic/flows/1/") return {
        id: 1,
        symptoms: [{ id: 11, key: "slow_crank" }, { id: 12, key: "engine_noise" }],
        causes: [],
      };
      return { id: 1, symptoms: [], causes: [] };
    });
    renderWizard(2);

    await user.click(await screen.findAllByRole("button", { name: "Remove symptom" }).then((buttons) => buttons[1]));

    await waitFor(() => expect(readDraft(71).flow.symptoms).toHaveLength(1));
    expect(api).toHaveBeenCalledWith("/mechanic/items/symptoms/12/", { method: "DELETE" });
  });

  it("removes an unwanted cause form without restarting the wizard", async () => {
    const user = userEvent.setup();
    const flow = baseFlow();
    flow.causes = [
      { key: "battery", name: "Weak battery", system: "electrical", commonness: "medium", links: {}, self_check: { steps: "", tools_needed: "", difficulty: "easy" }, costs: [] },
      { key: "starter", name: "", system: "general", commonness: "medium", links: {}, self_check: { steps: "", tools_needed: "", difficulty: "easy" }, costs: [] },
    ];
    writeDraft(71, { flowId: 1, step: 3, flow });
    api.mockImplementation(async (path) => {
      if (path === "/mechanic/flows/1/") return {
        id: 1,
        symptoms: [{ id: 11, key: "slow_crank" }],
        causes: [{ id: 21, name: "Weak battery" }],
      };
      return { id: 1, symptoms: [], causes: [] };
    });
    renderWizard(3);

    await user.click(await screen.findAllByRole("button", { name: "Remove cause" }).then((buttons) => buttons[0]));

    await waitFor(() => expect(readDraft(71).flow.causes).toHaveLength(1));
    expect(api).toHaveBeenCalledWith("/mechanic/items/causes/21/", { method: "DELETE" });
    expect(screen.getAllByLabelText("Possible cause")).toHaveLength(1);
  });
});
