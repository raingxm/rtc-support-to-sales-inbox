import { z } from "zod";

export const owners = ["Maya Chen", "Jordan Lee"] as const;
const ownerSchema = z.enum(owners);
export type Owner = z.infer<typeof ownerSchema>;

const evidenceSpanSchema = z.object({
  message: z.int().nonnegative(),
  start: z.int().nonnegative(),
  end: z.int().positive(),
}).refine(({ start, end }) => start < end);
export type EvidenceSpan = z.infer<typeof evidenceSpanSchema>;

const assessmentFields = {
  summary: z.string(),
  support_steps: z.array(z.string()),
  questions: z.array(z.string()),
};

const triageSchema = z.discriminatedUnion("kind", [
  z.object({
    kind: z.literal("mixed"),
    ...assessmentFields,
    evidence: z.array(evidenceSpanSchema).min(1),
  }),
  z.object({ kind: z.enum(["support", "clarify"]), ...assessmentFields }),
]);

const replySchema = z.object({
  body: z.string(),
  author: z.string().nullable(),
});
export type Reply = z.infer<typeof replySchema>;

const ticketSchema = z.object({
  id: z.string(),
  title: z.string(),
  customer: z.string(),
  messages: z.array(z.object({ body: z.string() })).min(1),
  status: z.literal("open"),
  origin: z.enum(["sample", "live"]),
  triage: triageSchema.nullable(),
  handoff: z.object({ owner: ownerSchema }).nullable(),
  confirmed_by: z.string().nullable(),
  withdrawn_by: z.string().nullable(),
  reply_draft: z.string().nullable(),
  reply_revision: z.int().nonnegative(),
  taken_over: z.boolean(),
  handed_back_by: z.string().nullable(),
  pending: z.object({
    reason: z.enum(["stopped-waiting", "documentation-unopened"]),
    waiting_seconds: z.int().nonnegative(),
  }).nullable(),
  replies: z.array(replySchema),
});

const ticketListSchema = z.array(ticketSchema);
export type Ticket = z.infer<typeof ticketSchema>;

const supportTokenKey = "rtc-support-token";
const supportNameKey = "rtc-support-name";

export class SupportSignInRequired extends Error {}
export class ReplyContextChanged extends Error {}

export function supportToken() {
  return sessionStorage.getItem(supportTokenKey) ?? "";
}

export function supportName() {
  return sessionStorage.getItem(supportNameKey) ?? "";
}

function supportHeaders(json = false): HeadersInit {
  const headers: Record<string, string> = {};
  if (json) headers["Content-Type"] = "application/json";
  const token = supportToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

function clearSupportSession() {
  sessionStorage.removeItem(supportTokenKey);
  sessionStorage.removeItem(supportNameKey);
}

export async function signIn(token: string) {
  const response = await fetch("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  if (response.status === 401) throw new SupportSignInRequired();
  if (!response.ok) throw new Error("Could not sign in");
  const person = z.object({ name: z.string().min(1) }).parse(await response.json());
  sessionStorage.setItem(supportTokenKey, token);
  sessionStorage.setItem(supportNameKey, person.name);
  return person.name;
}

export async function listTickets(signal?: AbortSignal) {
  const response = await fetch("/api/tickets", {
    cache: "no-store",
    signal,
    headers: supportHeaders(),
  });
  if (response.status === 401) {
    clearSupportSession();
    throw new SupportSignInRequired();
  }
  if (!response.ok) throw new Error("Could not load tickets");
  return ticketListSchema.parse(await response.json());
}

export class LetterSubmissionError extends Error {}

const rejectedQuoteSchema = z.object({
  detail: z.literal("not-in-letter"),
  quote: z.string(),
});

async function submittedTicket(response: Response, fallback: string) {
  if (response.status === 401) {
    clearSupportSession();
    throw new SupportSignInRequired();
  }
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
        `Analysis could not find this quote in the letter. "${rejection.data.quote}" Review the original message and try again.`,
      );
    }
    throw new LetterSubmissionError("The letter or its analysis could not be checked. Review the message and try again.");
  }
  if (!response.ok) throw new Error(fallback);
  return ticketSchema.parse(await response.json());
}

export async function submitLetter(letter: { customer: string; body: string }) {
  const response = await fetch("/api/tickets", {
    method: "POST",
    headers: supportHeaders(true),
    body: JSON.stringify(letter),
    signal: AbortSignal.timeout(45000),
  });
  return submittedTicket(response, "Could not analyze the letter");
}

export async function fetchTicket(ticketId: string, signal?: AbortSignal) {
  const response = await fetch("/api/tickets/" + encodeURIComponent(ticketId), {
    cache: "no-store",
    signal,
    headers: supportHeaders(),
  });
  if (response.status === 401) {
    clearSupportSession();
    throw new SupportSignInRequired();
  }
  if (response.status === 404) return null;
  if (!response.ok) throw new Error("Could not load ticket");
  return ticketSchema.parse(await response.json());
}

export async function createHandoff(ticketId: string, owner: Owner) {
  const response = await fetch(
    "/api/tickets/" + encodeURIComponent(ticketId) + "/handoff",
    {
      method: "POST",
      headers: supportHeaders(true),
      body: JSON.stringify({ owner }),
      signal: AbortSignal.timeout(8000),
    },
  );
  if (response.status === 401) {
    clearSupportSession();
    throw new SupportSignInRequired();
  }
  if (!response.ok) throw new Error("Could not confirm handoff");
  return ticketSchema.parse(await response.json());
}

export async function withdrawHandoff(ticketId: string) {
  const response = await fetch(
    "/api/tickets/" + encodeURIComponent(ticketId) + "/withdrawal",
    { method: "POST", headers: supportHeaders(), signal: AbortSignal.timeout(8000) },
  );
  if (response.status === 401) {
    clearSupportSession();
    throw new SupportSignInRequired();
  }
  if (!response.ok) throw new Error("Could not withdraw handoff");
  return ticketSchema.parse(await response.json());
}

export async function handBack(ticketId: string) {
  const response = await fetch(
    "/api/tickets/" + encodeURIComponent(ticketId) + "/handback",
    { method: "POST", headers: supportHeaders(), signal: AbortSignal.timeout(8000) },
  );
  if (response.status === 401) {
    clearSupportSession();
    throw new SupportSignInRequired();
  }
  if (!response.ok) throw new Error("Could not hand this back");
  return ticketSchema.parse(await response.json());
}

export async function sendReply(ticketId: string, body: string, revision: number) {
  const response = await fetch(
    "/api/tickets/" + encodeURIComponent(ticketId) + "/replies",
    {
      method: "POST",
      headers: supportHeaders(true),
      body: JSON.stringify({ body, expected_revision: revision }),
      signal: AbortSignal.timeout(8000),
    },
  );
  if (response.status === 401) {
    clearSupportSession();
    throw new SupportSignInRequired();
  }
  if (response.status === 409) throw new ReplyContextChanged();
  if (response.status === 422) throw new LetterSubmissionError("Write a reply before sending it.");
  if (!response.ok) throw new Error("Could not send the reply");
  return ticketSchema.parse(await response.json());
}

const customerSchema = z.object({
  id: z.string(),
  credential: z.string().min(1),
  title: z.string(),
  customer: z.string(),
  messages: z.array(z.object({ body: z.string() })).min(1),
  replies: z.array(replySchema),
});
export type CustomerTicket = z.infer<typeof customerSchema>;

async function customerTicket(response: Response, fallback: string) {
  if (response.status === 503) {
    throw new LetterSubmissionError("Live analysis is unavailable. Ask the workspace administrator to configure it.");
  }
  if (response.status === 502) {
    throw new LetterSubmissionError("Analysis failed. The ticket was kept. Open it again from the address you were given.");
  }
  if (response.status === 422) {
    const rejection = rejectedQuoteSchema.safeParse(await response.json());
    if (rejection.success) {
      throw new LetterSubmissionError(
        `That message could not be checked. "${rejection.data.quote}" Try again.`,
      );
    }
    throw new LetterSubmissionError("Write a message and try again.");
  }
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(fallback);
  return customerSchema.parse(await response.json());
}

export async function openCustomerTicket(letter: { customer: string; body: string }) {
  const response = await fetch("/api/customer-tickets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(letter),
    signal: AbortSignal.timeout(45000),
  });
  const ticket = await customerTicket(response, "Could not open the ticket");
  if (!ticket) throw new Error("Could not open the ticket");
  return ticket;
}

export async function fetchCustomerTicket(ticketId: string, credential: string, signal?: AbortSignal) {
  const response = await fetch(
    "/api/customer-tickets/" + encodeURIComponent(ticketId) + "/" + encodeURIComponent(credential),
    { cache: "no-store", signal },
  );
  return customerTicket(response, "Could not load ticket");
}

export async function appendCustomerMessage(ticketId: string, credential: string, body: string) {
  const response = await fetch(
    "/api/customer-tickets/" + encodeURIComponent(ticketId) + "/" + encodeURIComponent(credential) + "/messages",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body }),
      signal: AbortSignal.timeout(45000),
    },
  );
  const ticket = await customerTicket(response, "Could not add the message");
  if (!ticket) throw new Error("Could not add the message");
  return ticket;
}
