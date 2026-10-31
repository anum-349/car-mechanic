// Runs the real React app against a live Django API (set VITE_API_URL).
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../src/App.jsx";
import { AuthProvider } from "../src/auth.jsx";

const WAIT = { timeout: 10000 };

function renderAt(path = "/login") {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

async function login(user) {
  await user.type(await screen.findByLabelText("Username"), "ali");
  await user.type(screen.getByLabelText("Password"), "Str0ng!pass99");
  await user.click(screen.getByRole("button", { name: "Log in" }));
  await screen.findByRole("heading", { name: /What's wrong with your car\?|Gari mein kya masla hai\?/ }, WAIT);
  const englishSwitch = screen.getByRole("button", { name: "EN" });
  if (englishSwitch.getAttribute("aria-pressed") !== "true") await user.click(englishSwitch);
  await screen.findByRole("heading", { name: "What's wrong with your car?" }, WAIT);
}

beforeEach(() => localStorage.clear());

describe("car owner journey", () => {
  it("rejects a wrong password with a clear message", async () => {
    const user = userEvent.setup();
    renderAt();
    await user.type(await screen.findByLabelText("Username"), "ali");
    await user.type(screen.getByLabelText("Password"), "nope");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert", {}, WAIT)).toHaveTextContent(/account|credentials|password/i);
  });

  it("asks questions, shows the answer, then checks a quote", async () => {
    const user = userEvent.setup();
    renderAt();
    await login(user);

    // start a diagnosis
    await user.click(screen.getByRole("link", { name: "Start diagnosis" }));
    await user.click(await screen.findByRole("button", { name: "No, none of these" }, WAIT));
    await user.click(await screen.findByRole("radio", { name: /Ali's Alto/ }, WAIT));
    const problem = screen.getByLabelText("Describe the problem in your own words");
    expect(problem).toBeRequired();
    await user.type(problem, "The engine turns over slowly and I hear a clicking sound when starting.");
    await user.click(screen.getByRole("button", { name: "Start diagnosis" }));

    // the conversation: system asks, owner answers
    expect(await screen.findByText(/We'll work out what's wrong/, {}, WAIT)).toBeInTheDocument();
    expect(await screen.findByText("What happens?", {}, WAIT)).toBeInTheDocument();
    // every question has a "Not sure" option
    expect(screen.getByRole("button", { name: "Not sure" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Only clicks" }));
    const preferredAnswers = [/only a click/i, /dim/i, /more than 2 years/i, /no recent/i, /no cng kit/i, /short hum/i, /never starts/i, /no unusual smell/i, /neither/i];
    for (let index = 0; index < preferredAnswers.length && !screen.queryByRole("heading", { name: "Weak battery" }); index += 1) {
      const group = screen.getByRole("group", { name: "Choose your answer" });
      const choices = within(group).getAllByRole("button");
      const choice = choices.find((item) => preferredAnswers[index].test(item.textContent)) || choices[0];
      const progress = screen.getByText(/^Question \d+$/).textContent;
      await user.click(choice);
      await waitFor(() => expect(screen.queryByRole("heading", { name: "Weak battery" }) || screen.queryByText(new RegExp(`^Question ${Number(progress.match(/\d+/)[0]) + 1}$`))).toBeTruthy(), WAIT);
    }
    expect(await screen.findByText(/that's enough to work with/, {}, WAIT)).toBeInTheDocument();

    // results
    expect(await screen.findByRole("heading", { name: "Weak battery" }, WAIT)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Bad starter" })).toBeInTheDocument();
    expect(screen.getByText("69%")).toBeInTheDocument();
    expect(screen.getByText(/PKR 9,000 to PKR 18,500/)).toBeInTheDocument();
    expect(screen.getByText(/Estimates only/)).toBeInTheDocument();

    // self-check loads on demand
    await user.click(screen.getAllByRole("button", { name: "What can I check myself?" })[0]);
    expect(await screen.findByText(/Check lights/, {}, WAIT)).toBeInTheDocument();

    // record what the mechanic found
    await user.selectOptions(screen.getByLabelText("The real problem was"), "Weak battery");
    await user.type(screen.getByLabelText("What you paid (PKR)"), "12000");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("button", { name: "Saved" }, WAIT)).toBeDisabled();

    // quote check, pre-filled from this diagnosis
    await user.click(screen.getByRole("link", { name: "Check a mechanic's quote" }));
    await user.type(await screen.findByLabelText("What did the mechanic say is wrong?"), "battery dead");
    await user.type(screen.getByLabelText("Price quoted (PKR)"), "90000");
    await waitFor(() => expect(screen.getByLabelText("Which repair is that?")).toHaveDisplayValue("Weak battery"));
    await user.click(screen.getByRole("button", { name: "Check this quote" }));
    expect(await screen.findByRole("heading", { name: "Looks too high" }, WAIT)).toBeInTheDocument();
    expect(screen.getByText(/Much higher than the typical/)).toBeInTheDocument();
  });

  it("resumes a finished diagnosis from history with the conversation rebuilt", async () => {
    const user = userEvent.setup();
    renderAt();
    await login(user);
    await user.click(screen.getAllByRole("link", { name: "History" })[0]);
    const row = await screen.findByRole("link", { name: /Weak battery|Car won't start/ }, WAIT);
    await user.click(row);
    expect(await screen.findByText("What happens?", {}, WAIT)).toBeInTheDocument();
    expect(screen.getByText("Only clicks")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Weak battery" }, WAIT)).toBeInTheDocument();
  });

  it("switches the interface to Roman Urdu", async () => {
    const user = userEvent.setup();
    renderAt();
    await login(user);
    await user.click(screen.getByRole("button", { name: "Roman" }));
    expect(await screen.findByRole("heading", { name: "Gari mein kya masla hai?" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "EN" })); // the choice is saved to the profile: put it back
    expect(await screen.findByRole("heading", { name: "What's wrong with your car?" })).toBeInTheDocument();
  });

  it("shows garage, mechanics and warning lights data", async () => {
    const user = userEvent.setup();
    renderAt();
    await login(user);

    await user.click(screen.getAllByRole("link", { name: "My cars" })[0]);
    expect(await screen.findByRole("heading", { name: "Ali's Alto" }, WAIT)).toBeInTheDocument();
    expect(screen.getByText(/45,000 km/)).toBeInTheDocument();

    await user.click(screen.getAllByRole("link", { name: "Mechanics" })[0]);
    expect(await screen.findByRole("heading", { name: "AutoFix Garage" }, WAIT)).toBeInTheDocument();
    expect(screen.getByText(/5 from 1 review/)).toBeInTheDocument();
    expect(screen.getByText("Verified")).toBeInTheDocument();

    await user.click(screen.getAllByRole("link", { name: "Warning lights" })[0]);
    expect(await screen.findByText("Battery light", {}, WAIT)).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Scanner codes" }));
    expect(await screen.findByText("P0301", {}, WAIT)).toBeInTheDocument();
  });

  it("adds a car by choosing make then model", async () => {
    const user = userEvent.setup();
    renderAt();
    await login(user);
    await user.click(screen.getAllByRole("link", { name: "My cars" })[0]);
    await user.click(await screen.findByRole("button", { name: "Add another car" }, WAIT));
    const makeOption = await screen.findByRole("option", { name: "Suzuki" });
    await user.selectOptions(screen.getByLabelText("Make"), makeOption);
    await waitFor(() => expect(within(screen.getByLabelText("Model")).getAllByRole("option").length).toBeGreaterThan(2), WAIT);
    const modelSelect = screen.getByLabelText("Model");
    await user.selectOptions(modelSelect, within(modelSelect).getByRole("option", { name: /Cultus/ }));
    await user.clear(screen.getByLabelText("Year"));
    await user.type(screen.getByLabelText("Year"), "2010"); // before the Cultus VXL existed
    await user.click(screen.getByRole("button", { name: "Save car" }));
    expect(await screen.findByRole("alert", {}, WAIT)).toHaveTextContent(/year/i);
  });
});
