import { z } from "zod";

export const owners = ["Maya Chen", "Jordan Lee"] as const;
const ownerSchema = z.enum(owners);
export type Owner = z.infer<typeof ownerSchema>;

const evidenceSpanSchema = z.object({
  start: z.int().nonnegative(),
  end: z.int().positive(),
}).refine(({ start, end }) => start < end);
export type EvidenceSpan = z.infer<typeof evidenceSpanSchema>;

const assessmentFields = {
  summary: z.string(),
  support_steps: z.array(z.string()),
  questions: z.array(z.string()),
};

const ticketSchema = z.object({
  id: z.string(),
  title: z.string(),
  customer: z.string(),
  body: z.string(),
  status: z.literal("open"),
  origin: z.enum(["sample", "live"]),
  triage: z.discriminatedUnion("kind", [
    z.object({
      kind: z.literal("mixed"),
      ...assessmentFields,
      evidence: z.array(evidenceSpanSchema).min(1),
    }),
    z.object({ kind: z.enum(["support", "clarify"]), ...assessmentFields }),
  ]),
  handoff: z.object({ owner: ownerSchema }).nullable(),
});

const ticketListSchema = z.array(ticketSchema);
export type Ticket = z.infer<typeof ticketSchema>;

export async function listTickets(signal?: AbortSignal) {
  const response = await fetch("/api/tickets", { cache: "no-store", signal });
  if (!response.ok) throw new Error("Could not load tickets");
  return ticketListSchema.parse(await response.json());
}

export class LetterSubmissionError extends Error {}

const rejectedQuoteSchema = z.object({
  detail: z.literal("not-in-letter"),
  quote: z.string(),
});

export async function submitLetter(letter: { customer: string; body: string }) {
  const response = await fetch("/api/tickets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(letter),
    signal: AbortSignal.timeout(45000),
  });

  if (response.status === 503) {
    throw new LetterSubmissionError("Live analysis is unavailable. Ask the workspace administrator to configure it.");
  }
  if (response.status === 502) {
    throw new LetterSubmissionError("Analysis failed. Try analyzing this letter again.");
  }
  if (response.status === 422) {
    const rejection = rejectedQuoteSchema.safeParse(await response.json());
    if (rejection.success) {
      throw new LetterSubmissionError(
        `Analysis could not find this quote in the letter. “${rejection.data.quote}” Review the original message and try again.`,
      );
    }
    throw new LetterSubmissionError("The letter or its analysis could not be checked. Review the message and try again.");
  }
  if (!response.ok) throw new Error("Could not analyze the letter");
  return ticketSchema.parse(await response.json());
}

export async function createHandoff(ticketId: string, owner: Owner) {
  const response = await fetch(
    "/api/tickets/" + encodeURIComponent(ticketId) + "/handoff",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ owner }),
      signal: AbortSignal.timeout(8000),
    },
  );
  if (!response.ok) throw new Error("Could not confirm handoff");
  return ticketSchema.parse(await response.json());
}
