import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../src/auth.jsx";
import DiagnosisChat from "../src/pages/DiagnosisChat.jsx";

vi.mock("../src/api.js", () => ({
  api: vi.fn(),
  trackEvent: vi.fn(() => Promise.resolve()),
  getStoredUser: () => null,
  getToken: () => null,
  setStoredUser: () => {},
  setToken: () => {},
  setRefresh: () => {},
}));

import { api } from "../src/api.js";

const question = {
  id: 19,
  text: "What happens when you turn the key?",
  media_url: "https://example.test/key.png",
  options: [
    { id: 31, label: "It clicks", is_unsure: false },
    { id: 32, label: "It starts slowly", is_unsure: false },
    { id: 33, label: "Not sure", is_unsure: true },
  ],
};

function renderDiagnosis() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <AuthProvider><MemoryRouter initialEntries={["/diagnose/1"]}><Routes><Route path="/diagnose/:id" element={<DiagnosisChat />} /></Routes></MemoryRouter></AuthProvider>
  </QueryClientProvider>);
}

function resumedQuestion(overrides = {}) {
  return { id: 1, status: "in_progress", answers: [], question, ...overrides };
}

describe("diagnosis response handling", () => {
  beforeEach(() => { localStorage.clear(); api.mockReset(); });

  it("renders a resumable question response, media and a dedicated Not sure action", async () => {
    api.mockResolvedValueOnce(resumedQuestion());
    renderDiagnosis();
    expect(await screen.findByRole("heading", { name: question.text })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: question.text })).toHaveAttribute("loading", "lazy");
    expect(screen.getByRole("button", { name: "Not sure" })).toBeInTheDocument();
    expect(screen.getByText("Question 1")).toBeInTheDocument();
  });

  it("shows mapped symptoms and lets the user remove one", async () => {
    let hasMappedSymptom = true;
    api.mockImplementation((path, options) => {
      if (options?.method === "DELETE") { hasMappedSymptom = false; return Promise.resolve({ removed: true }); }
      return Promise.resolve(resumedQuestion({ understood_symptoms: hasMappedSymptom ? [{ id: 44, text: "Fuel smell" }] : [] }));
    });
    const user = userEvent.setup();
    renderDiagnosis();
    expect(await screen.findByText("Fuel smell")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove Fuel smell" }));
    await waitFor(() => expect(screen.queryByText("Fuel smell")).not.toBeInTheDocument());
    expect(api).toHaveBeenCalledWith("/sessions/1/free-text/", { method: "DELETE", body: { symptom: 44 } });
  });

  it("shows StopDriving for a stop response and never shows ranked results", async () => {
    api.mockResolvedValueOnce(resumedQuestion()).mockResolvedValueOnce({ stop: true, message: "Do not drive because of smoke." });
    const user = userEvent.setup();
    renderDiagnosis();
    await user.click(await screen.findByRole("button", { name: "It clicks" }));
    expect(await screen.findByRole("heading", { name: "Do not drive this car" })).toBeInTheDocument();
    expect(screen.getByText("Do not drive because of smoke.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Most likely causes" })).not.toBeInTheDocument();
  });

  it("renders the result from a done response", async () => {
    api.mockResolvedValueOnce({ id: 1, status: "completed", done: true, result: {
      id: 1, results: [], message: "Not enough information.",
      free_text: "The engine cranks slowly.",
      answers: [{ question: "Does the dashboard light up?", answer: "Not sure" }],
    } });
    renderDiagnosis();
    expect(await screen.findByRole("heading", { name: "Your diagnosis" })).toBeInTheDocument();
    expect(screen.getByText("Not enough information.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Evidence collected" })).toBeInTheDocument();
    expect(screen.getByText("The engine cranks slowly.")).toBeInTheDocument();
    expect(screen.getByText("Does the dashboard light up?").closest("li")).toHaveTextContent("Not sure");
  });

  it("requests clarification when text has no reliable symptom match", async () => {
    api.mockImplementation((path, options) => {
      if (options?.method === "POST") return Promise.resolve({
        done: false,
        question: { ...question, text: "Does it happen while starting?" },
      });
      return Promise.resolve({
        id: 1, diagnosis_type: "text", status: "in_progress",
        answers: [], clarification_required: true,
      });
    });
    const user = userEvent.setup();
    renderDiagnosis();
    await user.type(await screen.findByLabelText("Add a detail about the problem"), "Only when starting");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("heading", {
      name: "Does it happen while starting?",
    })).toBeInTheDocument();
    expect(api).toHaveBeenCalledWith("/sessions/1/free-text/", {
      method: "POST", body: { text: "Only when starting" },
    });
  });

  it("uses a returned next-question response and blocks duplicate submissions", async () => {
    let resolveAnswer;
    const secondQuestion = { ...question, id: 20, text: "Does the dashboard light up?" };
    api.mockImplementation((path, options) => {
      if (options?.method === "POST") return new Promise((resolve) => { resolveAnswer = resolve; });
      return Promise.resolve(resumedQuestion());
    });
    const user = userEvent.setup();
    renderDiagnosis();
    const first = await screen.findByRole("button", { name: "It clicks" });
    await user.click(first);
    await waitFor(() => expect(first).toBeDisabled());
    fireEvent.click(first);
    expect(api.mock.calls.filter(([, options]) => options?.method === "POST")).toHaveLength(1);
    resolveAnswer({ done: false, question: secondQuestion });
    expect(await screen.findByRole("heading", { name: secondQuestion.text })).toBeInTheDocument();
    expect(api).toHaveBeenCalledWith("/sessions/1/answer/", { method: "POST", body: { question: question.id, option: 31 } });
  });
});
