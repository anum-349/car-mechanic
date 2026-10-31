import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { toBlob } from "html-to-image";
import { AuthProvider } from "../src/auth.jsx";
import ConfidenceBar from "../src/components/ConfidenceBar.jsx";
import ShareCard from "../src/components/ShareCard.jsx";

vi.mock("html-to-image", () => ({ toBlob: vi.fn() }));

describe("result components", () => {
  beforeEach(() => localStorage.clear());

  it("shows the confidence band and rounds the secondary confidence label", () => {
    render(<AuthProvider><ConfidenceBar confidence={0.873} band="likely" /></AuthProvider>);
    expect(screen.getByText("Likely")).toBeInTheDocument();
    expect(screen.getByText("About 85%" )).toBeInTheDocument();
  });

  it("renders the 360px share card structure", () => {
    const { getByTestId } = render(<AuthProvider><ShareCard result={{}} topCause={{ cause_name: "Weak battery", band: "very likely", cost: { total_min: 9000, total_max: 18500 } }} /></AuthProvider>);
    const card = getByTestId("share-card");
    expect(card).toHaveStyle({ width: "360px" });
    expect(card).toMatchSnapshot();
  });

  it("skips embedding cross-origin fonts when exporting the share card", async () => {
    toBlob.mockResolvedValue(null);
    const { getByTestId } = render(<AuthProvider><ShareCard result={{}} topCause={{ cause_name: "Weak battery" }} /></AuthProvider>);

    fireEvent.click(screen.getByRole("button", { name: "Share result" }));

    await waitFor(() => {
      expect(toBlob).toHaveBeenCalledWith(getByTestId("share-card"), expect.objectContaining({ skipFonts: true }));
    });
  });
});
