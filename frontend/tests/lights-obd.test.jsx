import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, getAll } from "../src/api.js";
import ObdLookup from "../src/pages/ObdLookup.jsx";
import WarningLights, { WarningLightSheet } from "../src/pages/WarningLights.jsx";
import { normalizeObdCode } from "../src/utils/obdCode.js";

vi.mock("../src/api.js", () => ({ api: vi.fn(), getAll: vi.fn() }));
vi.mock("../src/auth.jsx", () => ({ useAuth: () => ({
  lang: "en",
  t: (key) => ({ lights_close: "Close details", lights_stop: "Stop now", lights_meaning: "What it means", lights_action: "What to do", lights_stop_advice: "See stop-driving advice", offline_cached: "You're offline. Showing saved information.", obd_intro: "Enter the code shown by your car's scanner.", obd_search_label: "OBD code", obd_search_hint: "For example P0301, B1234, C1234 or U0100.", obd_search: "Look up code", obd_invalid: "Enter a valid code, such as P0301 or U0100.", page_obd: "OBD code lookup", obd_system: "System", obd_causes: "Likely causes", obd_causes_empty: "No likely causes are listed for this code yet.", obd_start_diagnosis: "Start a diagnosis with this code" })[key] || key,
}) }));

function renderWithProviders(element) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter>{element}</MemoryRouter></QueryClientProvider>);
}

describe("OBD code normalization", () => {
  it("trims, uppercases and accepts P, B, C and U families", () => {
    expect(normalizeObdCode("  p0301 ")).toBe("P0301");
    for (const code of ["B1234", "C1234", "U0100"]) expect(normalizeObdCode(code)).toBe(code);
  });

  it("rejects incomplete or malformed codes", () => {
    for (const code of ["", "P301", "X0301", "P03G1", "P03011"]) expect(normalizeObdCode(code)).toBeNull();
  });
});

describe("warning light details sheet", () => {
  it("shows meaning, severity, action and closes accessibly", async () => {
    const onClose = vi.fn();
    renderWithProviders(<WarningLightSheet light={{ id: 7, name: "Oil pressure", severity: "stop_now", meaning: "Pressure is low", recommended_action: "Stop safely" }} onClose={onClose} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Stop now")).toBeInTheDocument();
    expect(screen.getByText("Pressure is low")).toBeInTheDocument();
    expect(screen.getByText("Stop safely")).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
  });

  it("keeps the previously viewed light list available when refresh fails offline", async () => {
    localStorage.setItem("garidoc-offline:warning-lights", JSON.stringify({ items: [
      { id: 1, name: "Saved battery light", severity: "repair_soon", meaning: "Saved meaning", recommended_action: "Saved action" },
    ], draft: false }));
    getAll.mockRejectedValue(new Error("offline"));
    renderWithProviders(<WarningLights />);
    expect(await screen.findByRole("button", { name: /Saved battery light/ })).toBeInTheDocument();
    expect(await screen.findByRole("status")).toHaveTextContent("You're offline. Showing saved information.");
  });
});

describe("OBD lookup page", () => {
  beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); });
  it("queries using the normalized code and shows the result", async () => {
    api.mockResolvedValue({ code: "P0301", description: "Cylinder misfire", system: "Engine", likely_causes: [] });
    renderWithProviders(<ObdLookup />);
    fireEvent.change(screen.getByLabelText("OBD code"), { target: { value: " p0301 " } });
    fireEvent.click(screen.getByRole("button", { name: "Look up code" }));
    expect(await screen.findByText("Cylinder misfire")).toBeInTheDocument();
    expect(api).toHaveBeenCalledWith("/obd/P0301/");
  });
});
