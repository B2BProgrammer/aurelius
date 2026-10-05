/** Unit tests: compliance rules, intent/tone, templates, the Claude writer, the composer. */
import assert from "node:assert/strict";
import { after, before, describe, it } from "node:test";

import { checkEmail, EMAIL_DISCLOSURE, redactForLlm } from "../src/compose/compliance.js";
import { buildPrompt } from "../src/compose/llm.js";
import { detectIntent, templateDraft, toneFromStyle } from "../src/compose/templates.js";
import type { InvokeContext } from "../src/contract.js";
import { FakeMessages, type FakeLiaison, HOUSEHOLDS, makeComposer, startFakeLiaison, testConfig } from "./helpers.js";

const ctx: InvokeContext = { trace_id: "unit-trace", user_id: "dev-advisor" };
const patel = HOUSEHOLDS["patel-001"]!;

describe("compliance", () => {
  it("removes promissory claims", () => {
    const { text, report } = checkEmail("This fund has guaranteed returns and is risk-free. It will definitely go up.");
    assert.ok(!/guaranteed returns|risk-free|definitely go up/i.test(text));
    assert.deepEqual(report.fixes.sort(), ["CMP_CERTAINTY", "CMP_GUARANTEE", "CMP_NO_RISK"]);
  });

  it("masks SSNs, card and account numbers", () => {
    const { text, report } = checkEmail("SSN 123-45-6789, card 4111 1111 1111 1111, account 123456789.");
    assert.ok(!text.includes("123-45-6789") && !text.includes("4111") && !text.includes("123456789"));
    assert.deepEqual(report.fixes.sort(), ["PII_ACCOUNT", "PII_CARD", "PII_SSN"]);
  });

  it("does not mask dollar amounts or dates", () => {
    const { report } = checkEmail("We moved $250,000 on 2026-10-08.");
    assert.deepEqual(report.fixes, []);
  });

  it("adds the disclosure when performance is mentioned, only once", () => {
    const first = checkEmail("Your portfolio returns were strong this year.");
    assert.ok(first.report.disclosure_added);
    assert.ok(first.text.endsWith(EMAIL_DISCLOSURE));
    const second = checkEmail(first.text);
    assert.equal(second.report.disclosure_added, false);
    assert.equal(second.text, first.text);
  });

  it("still adds the disclosure when the performance claim itself was removed", () => {
    const { text, report } = checkEmail("It offers guaranteed returns of 6%.");
    assert.ok(report.fixes.includes("CMP_GUARANTEE"));
    assert.ok(report.disclosure_added && text.includes("possible loss of principal"));
  });

  it("no disclosure for a plain scheduling email", () => {
    assert.equal(checkEmail("Can we meet Tuesday at 10?").report.disclosure_added, false);
  });

  it("warns about links and leftover placeholders", () => {
    const { report } = checkEmail("See https://example.com and call [client name].");
    assert.equal(report.warnings.length, 2);
  });

  it("masks PII before text goes to the LLM", () => {
    assert.equal(redactForLlm("SSN 123-45-6789"), "SSN [SSN]");
  });
});

describe("intent and tone", () => {
  const cases: Array<[string, string]> = [
    ["Follow up on today's review meeting", "meeting_follow_up"],
    ["Recap of our call", "meeting_follow_up"],
    ["Reschedule our review", "scheduling"],
    ["Thank them for the referral", "thank_you"],
    ["Prepare for the upcoming review", "meeting_prep"],
    ["Say hello", "check_in"],
  ];
  for (const [purpose, intent] of cases) {
    it(`"${purpose}" -> ${intent}`, () => assert.equal(detectIntent(purpose), intent));
  }

  it("reads the tone from the household's style note", () => {
    assert.equal(toneFromStyle("Formal. Prefers a call."), "formal");
    assert.equal(toneFromStyle("Prefers short, plain-language emails."), "brief");
    assert.equal(toneFromStyle("Chatty and warm"), "warm");
    assert.equal(toneFromStyle(undefined), "warm");
  });
});

describe("template", () => {
  it("uses CRM facts: salutation, tasks by owner, review date, signature", () => {
    const { subject, body } = templateDraft({
      purpose: "follow up", points: ["we agreed to raise the 529 contribution"], intent: "meeting_follow_up",
      tone: "brief", household: patel, signature: "Sam Rivera\nAurelius Wealth",
    });
    assert.equal(subject, "Following up on our conversation");
    assert.ok(body.startsWith("Hi Raj and Anita,"));
    assert.match(body, /- We agreed to raise the 529 contribution\./);
    assert.match(body, /items on your side:\n- Send updated beneficiary form\./);
    assert.match(body, /On my side, I'm working on:\n- Model retirement at 62 and 63\./);
    assert.match(body, /Thursday, October 8/);
    assert.ok(body.endsWith("Thanks,\nSam Rivera\nAurelius Wealth"));
  });

  it("is neutral without a household", () => {
    const { body } = templateDraft({ purpose: "say hello", points: [], intent: "check_in", tone: "formal",
                                     household: null, signature: "Sam" });
    assert.ok(body.startsWith("Dear Client,"));
    assert.ok(!body.includes("say hello"), "the purpose is an instruction, never pasted in");
    assert.ok(body.includes("[Add your key points]"));
    assert.ok(checkEmail(body, { signature: "Sam" }).report.warnings.some((w) => w.includes("placeholder")));
  });
});

describe("Claude writer (fake SDK)", () => {
  it("sends a forced tool call with minimum data and redacted advisor text", async () => {
    const fake = new FakeMessages({ subject: "Recap", body: "Hi Raj and Anita,\n\nGreat meeting today, thank you.\n\nThanks,\nSam Rivera\nAurelius Wealth" });
    const composer = makeComposer(testConfig({ liaisonUrl: "http://127.0.0.1:1" }), fake);
    await composer.draft({ client_id: "patel-001", purpose: "Follow up. Raj SSN 123-45-6789", points: [] }, ctx);
    const call = fake.calls[0]!;
    assert.deepEqual(call.tool_choice, { type: "tool", name: "write_email" });
    const prompt = JSON.stringify(call.messages);
    assert.ok(!prompt.includes("123-45-6789"), "SSN must not reach the LLM");
    assert.ok(prompt.includes("<advisor_request>"));
  });

  it("buildPrompt never includes emails or phones", () => {
    const p = buildPrompt({ intent: "check_in", tone: "warm", purpose: "hi", points: [], household: patel,
                            template: { subject: "s", body: "b" }, signature: "Sam", traceId: "t" });
    assert.ok(!p.includes("@example.com") && !p.includes("0142"));
  });
});

describe("composer (fake Liaison)", () => {
  let liaison: FakeLiaison;
  before(async () => { liaison = await startFakeLiaison(); });
  after(async () => { await liaison.close(); });

  it("personalizes from the Liaison and passes the token + trace id", async () => {
    const composer = makeComposer(testConfig({ liaisonUrl: liaison.url }));
    const r = await composer.draft({ client_id: "patel-001", purpose: "Follow up on the review", points: [] }, ctx);
    assert.equal(r.personalized, true);
    assert.equal(r.tone, "brief");
    assert.deepEqual(r.to, ["Raj Patel <r***@example.com>", "Anita Patel <a***@example.com>"]);
    assert.equal(r.requires_approval, true);
    assert.equal(r.drafted_by, "template");
    const last = liaison.calls.at(-1)!;
    assert.equal(last.trace, "unit-trace");
    assert.equal(last.body["skill"], "get_household");
  });

  it("uses Claude's draft when valid, but still runs compliance on it", async () => {
    const fake = new FakeMessages({
      subject: "Your review",
      body: "Hi Raj and Anita,\n\nThis plan has guaranteed returns.\n\nThanks,\nSam Rivera\nAurelius Wealth",
    });
    const composer = makeComposer(testConfig({ liaisonUrl: liaison.url }), fake);
    const r = await composer.draft({ client_id: "patel-001", purpose: "Check in", points: [] }, ctx);
    assert.equal(r.drafted_by, "claude-haiku-4-5-20251001");
    assert.ok(r.compliance.fixes.includes("CMP_GUARANTEE"));
    assert.ok(!r.body.includes("guaranteed returns"));
    assert.ok(r.compliance.disclosure_added);
  });

  it("falls back to the template when Claude returns junk or throws", async () => {
    for (const reply of [{ subject: "x" }, new Error("overloaded")]) {
      const composer = makeComposer(testConfig({ liaisonUrl: liaison.url }), new FakeMessages(reply));
      const r = await composer.draft({ client_id: "patel-001", purpose: "Check in", points: [] }, ctx);
      assert.equal(r.drafted_by, "template (llm_fallback)");
      assert.ok(r.body.startsWith("Hi Raj and Anita,"));
    }
  });

  it("appends the signature if Claude forgot it", async () => {
    const fake = new FakeMessages({ subject: "Hello", body: "Hi Raj and Anita,\n\nJust checking in on things.\n\nBest," });
    const composer = makeComposer(testConfig({ liaisonUrl: liaison.url }), fake);
    const r = await composer.draft({ client_id: "patel-001", purpose: "Check in", points: [] }, ctx);
    assert.ok(r.body.includes("Sam Rivera\nAurelius Wealth"));
  });

  it("warns when the household prefers phone", async () => {
    const composer = makeComposer(testConfig({ liaisonUrl: liaison.url }));
    const r = await composer.draft({ client_id: "chen-002", purpose: "Prepare for our upcoming review", points: [] }, ctx);
    assert.equal(r.tone, "formal");
    assert.ok(r.body.startsWith("Dear Mr. and Mrs. Chen,"));
    assert.ok(r.warnings.some((w) => w.includes("prefers phone")));
  });

  it("unknown client is an error, not a generic email", async () => {
    const composer = makeComposer(testConfig({ liaisonUrl: liaison.url }));
    await assert.rejects(composer.draft({ client_id: "nobody-1", purpose: "hello there", points: [] }, ctx), /No household/);
  });

  it("degrades gracefully when the Liaison is down or slow", async () => {
    for (const mode of ["down", "slow"] as const) {
      liaison.mode = mode;
      const composer = makeComposer(testConfig({ liaisonUrl: liaison.url, liaisonTimeoutMs: 200 }));
      const r = await composer.draft({ client_id: "patel-001", purpose: "Check in", points: [] }, ctx);
      assert.equal(r.personalized, false);
      assert.ok(r.body.startsWith("Hello,"));
      assert.ok(r.warnings[0]?.startsWith("CRM unavailable"));
    }
    liaison.mode = "ok";
  });

  it("review_email flags a greeting that doesn't match the household", async () => {
    const composer = makeComposer(testConfig({ liaisonUrl: liaison.url }));
    const r = await composer.review({ client_id: "patel-001", text: "Dear Sir or Madam,\n\nThanks for your time.\n\nSam" }, ctx);
    assert.equal(r.changed, false);
    assert.equal(r.verdict, "ready_for_approval");
    assert.ok(r.warnings.some((w) => w.includes("usual greeting")));
  });
});
