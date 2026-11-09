import { z } from "zod";

export const owners = ["Maya Chen", "Jordan Lee"] as const;
const ownerSchema = z.enum(owners);
export type Owner = z.infer<typeof ownerSchema>;

const ticketSchema = z.object({
  id: z.string(),
  title: z.string(),
  customer: z.string(),
  body: z.string(),
  status: z.literal("open"),
  triage: z.object({
    kind: z.enum(["mixed", "support", "clarify"]),
    summary: z.string(),
    support_steps: z.array(z.string()),
    evidence: z.array(z.string()),
    questions: z.array(z.string()),
  }),
  handoff: z.object({ owner: ownerSchema }).nullable(),
});

const ticketListSchema = z.array(ticketSchema);
export type Ticket = z.infer<typeof ticketSchema>;

export async function listTickets(signal?: AbortSignal) {
  const response = await fetch("/api/tickets", { cache: "no-store", signal });
  if (!response.ok) throw new Error("Could not load tickets");
  return ticketListSchema.parse(await response.json());
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
