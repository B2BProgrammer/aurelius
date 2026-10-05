import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Overview } from "../src/api/types";
import { App } from "../src/App";
import { PASS, fakeConductor, fakeJwt, json, renderApp, signedIn } from "./helpers";

describe("sign in", () => {
  it("signs in and lands on the households", async () => {
    const { calls } = fakeConductor((url) =>
      url === "/v1/auth/login"
        ? json({ access_token: fakeJwt(), token_type: "bearer", expires_in: 3600, user: "advisor" })
        : PASS(),
    );
    renderApp(<App />);
    await userEvent.type(screen.getByLabelText("Password"), "a-long-dev-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText(/Good to see you, advisor/)).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Patel" })).toBeInTheDocument();
    expect(calls[0]?.body).toEqual({ username: "advisor", password: "a-long-dev-password" });
    expect(sessionStorage.getItem("atrium.session")).toContain("advisor");
  });

  it("says plainly when the password is wrong, and clears it", async () => {
    fakeConductor((url) => (url === "/v1/auth/login" ? json({ detail: "Wrong username or password" }, 401) : PASS()));
    renderApp(<App />);
    await userEvent.type(screen.getByLabelText("Password"), "nope");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That username and password don't match.");
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });

  it("explains how to switch sign-in on", async () => {
    fakeConductor((url) => (url === "/v1/auth/login" ? json({ detail: "disabled" }, 404) : PASS()));
    renderApp(<App />);
    await userEvent.type(screen.getByLabelText("Password"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("DEV_LOGIN_PASSWORD");
  });
});

describe("dossier", () => {
  it("shows the household, what needs the advisor, and which agents answered", async () => {
    signedIn();
    fakeConductor();
    renderApp(<App />, "/clients/patel-001");
    expect(await screen.findByRole("heading", { level: 1, name: "Patel household" })).toBeInTheDocument();
    expect(screen.getByText("$2.35M")).toBeInTheDocument();

    const strip = screen.getByLabelText("Agents that prepared this file");
    for (const name of ["Liaison", "Analyst", "Notary", "Actuary", "Pulse", "Scribe"]) {
      expect(within(strip).getByText(name)).toBeInTheDocument();
    }

    const needs = screen.getByRole("region", { name: "Needs you" });
    expect(within(needs).getByText(/driver's license expires/)).toBeInTheDocument();
    expect(within(needs).getByText("Stocks are 8 points over target.")).toBeInTheDocument();

    // Retirement comes from a separate Actuary call
    expect(await screen.findByText("87%")).toBeInTheDocument();
  });

  it("says which agent didn't answer and keeps the rest of the file", async () => {
    signedIn();
    fakeConductor(async (url) => {
      if (url !== "/v1/clients/patel-001/overview") return PASS();
      const { overview } = await import("./helpers");
      const o = structuredClone(overview) as unknown as Overview;
      o.sections.events = { ...o.sections.events, status: "error", error: "pulse timed out after 10s" };
      return json(o);
    });
    renderApp(<App />, "/clients/patel-001");
    expect(await screen.findByText(/Pulse didn't answer: pulse timed out/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Patel household" })).toBeInTheDocument();
  });

  it("shows a not-found message for an unknown household", async () => {
    signedIn();
    fakeConductor();
    renderApp(<App />, "/clients/nobody-999");
    expect(await screen.findByText(/no household with the id nobody-999/)).toBeInTheDocument();
  });

  it("drafts an email but won't approve it while placeholders remain", async () => {
    signedIn();
    const { calls } = fakeConductor((url) =>
      url === "/v1/drafts/approve"
        ? json({ approved: true, note_id: "N-5100", next_step: "Send it from your own mailbox.", guardrail_notes: [] })
        : PASS(),
    );
    renderApp(<App />, "/clients/patel-001");
    await userEvent.click(await screen.findByRole("button", { name: "Draft email" }));

    const approve = await screen.findByRole("button", { name: "Approve and log to CRM" });
    expect(approve).toBeDisabled(); // the template still says [Add your key points]

    const body = screen.getByLabelText("Email body");
    await userEvent.clear(body);
    await userEvent.type(body, "Hi Raj and Anita, the two retirement scenarios are attached. Thanks, Sam");
    expect(approve).toBeEnabled();
    await userEvent.click(approve);

    expect(await screen.findByRole("status")).toHaveTextContent("note N-5100");
    const sent = calls.find((c) => c.url === "/v1/drafts/approve")?.body as { client_id: string; body: string };
    expect(sent.client_id).toBe("patel-001");
    expect(sent.body).toMatch(/retirement scenarios/);
  });

  it("shows Sentinel's revised text when approval is refused", async () => {
    signedIn();
    fakeConductor((url) =>
      url === "/v1/drafts/approve"
        ? json({
            approved: false,
            reason: "The security check changed the text. Review the revised version.",
            revised_body: "Hi Raj, this fund is [removed: non-compliant claim].",
            guardrail_notes: [],
          })
        : PASS(),
    );
    renderApp(<App />, "/clients/patel-001");
    await userEvent.click(await screen.findByRole("button", { name: "Draft email" }));
    const body = await screen.findByLabelText("Email body");
    await userEvent.clear(body);
    await userEvent.type(body, "Hi Raj, this fund has guaranteed returns.");
    await userEvent.click(screen.getByRole("button", { name: "Approve and log to CRM" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("security check changed the text");
    await waitFor(() => expect(body).toHaveValue("Hi Raj, this fund is [removed: non-compliant claim]."));
  });
});
