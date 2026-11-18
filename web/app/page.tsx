"use client";

import {
  Activity, ArrowRight, Check, ChevronRight, CircleHelp,
  Headset, Inbox, Route, ScanLine, Wrench,
} from "lucide-react";
import { type FormEvent, type ReactNode, type Ref, useEffect, useRef, useState } from "react";
import { DeskFrame } from "./frame";
import {
  createHandoff, LetterSubmissionError, listTickets, owners, sendReply, signIn, submitLetter,
  supportName, supportToken, SupportSignInRequired, type EvidenceSpan, type Owner, type Ticket,
} from "../lib/tickets";

const kindLabels = {
  mixed: "Opportunity",
  support: "Support only",
  clarify: "Needs context",
};

const pendingLabels = {
  "stopped-waiting": "Stopped waiting",
};

type InboxState =
  | { status: "loading" }
  | { status: "signed-out" }
  | { status: "error" }
  | { status: "ready"; tickets: Ticket[]; name: string };

function TicketList({ tickets, selectedId, onSelect }: {
  tickets: Ticket[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <aside className="queue" aria-labelledby="queue-heading">
      <div className="queue-header">
        <span className="queue-title"><Inbox size={17} /><h2 id="queue-heading">Ticket queue</h2></span>
        <span className="count">{tickets.length}</span>
      </div>
      <ul className="queue-list">
        {tickets.map((ticket) => (
          <li key={ticket.id}>
            <button
              className="queue-item"
              type="button"
              aria-pressed={ticket.id === selectedId}
              onClick={() => onSelect(ticket.id)}
            >
              <span className="queue-meta">
                <span className="mono">{ticket.id}</span>
                <ChevronRight size={15} />
              </span>
              <strong>{ticket.title}</strong>
              <span className="queue-customer">{ticket.customer}</span>
              <span className={"badge " + (ticket.pending ? "pending" : ticket.triage?.kind ?? "")}>
                {ticket.handoff
                  ? "Handoff assigned"
                  : ticket.pending
                    ? pendingLabels[ticket.pending.reason]
                    : ticket.triage
                      ? kindLabels[ticket.triage.kind]
                      : "Open"}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}

type LetterSubmission =
  | { status: "idle" | "invalid" | "pending" }
  | { status: "error"; message: string };

function NewLetterForm({ onCreated }: { onCreated: (ticket: Ticket) => void }) {
  const [customer, setCustomer] = useState("");
  const [body, setBody] = useState("");
  const [submission, setSubmission] = useState<LetterSubmission>({ status: "idle" });
  const disclosure = useRef<HTMLDetailsElement>(null);
  const customerField = useRef<HTMLInputElement>(null);
  const messageField = useRef<HTMLTextAreaElement>(null);
  const pending = submission.status === "pending";
  const customerInvalid = submission.status === "invalid" && !customer.trim();
  const messageInvalid = submission.status === "invalid" && !body.trim();

  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    if (!customer.trim() || !body.trim()) {
      setSubmission({ status: "invalid" });
      (customer.trim() ? messageField : customerField).current?.focus();
      return;
    }

    setSubmission({ status: "pending" });
    try {
      const ticket = await submitLetter({ customer: customer.trim(), body });
      setCustomer("");
      setBody("");
      setSubmission({ status: "idle" });
      if (disclosure.current) disclosure.current.open = false;
      onCreated(ticket);
    } catch (error) {
      setSubmission({
        status: "error",
        message: error instanceof LetterSubmissionError
          ? error.message
          : "Could not confirm the result. Check the ticket queue before trying again.",
      });
    }
  }

  return (
    <details className="letter-intake" ref={disclosure}>
      <summary><ScanLine size={17} /><strong>New letter</strong><ChevronRight size={16} /></summary>
      <form className="letter-form" onSubmit={analyze} noValidate aria-busy={pending}>
        <label htmlFor="letter-customer">Customer name</label>
        <input
          id="letter-customer" ref={customerField} value={customer} required disabled={pending}
          aria-invalid={customerInvalid} aria-describedby={customerInvalid ? "letter-customer-error" : undefined}
          onChange={(event) => setCustomer(event.target.value)}
        />
        {customerInvalid && <p className="error-note" id="letter-customer-error">Enter the customer's name.</p>}
        <label htmlFor="letter-message">Customer message</label>
        <textarea
          id="letter-message" ref={messageField} value={body} rows={5} required disabled={pending}
          aria-invalid={messageInvalid} aria-describedby={messageInvalid ? "letter-message-error" : undefined}
          onChange={(event) => setBody(event.target.value)}
        />
        {messageInvalid && <p className="error-note" id="letter-message-error">Paste the customer's original message.</p>}
        <button className="action" type="submit" disabled={pending}>
          <span>{pending ? "Analyzing…" : "Analyze letter"}</span>
          <ArrowRight size={16} />
        </button>
        {submission.status === "error" && <p className="error-note" role="alert">{submission.message}</p>}
      </form>
    </details>
  );
}

function HandoffForm({ ticket, onUpdated }: {
  ticket: Ticket;
  onUpdated: (ticket: Ticket) => void;
}) {
  const [owner, setOwner] = useState<Owner | "">("");
  const [submission, setSubmission] = useState<"idle" | "pending" | "error">("idle");
  const result = useRef<HTMLDivElement>(null);
  const pending = submission === "pending";

  useEffect(() => {
    if (ticket.handoff && pending) result.current?.focus();
  }, [ticket.handoff, pending]);

  async function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!owner || pending) return;

    setSubmission("pending");
    try {
      onUpdated(await createHandoff(ticket.id, owner));
    } catch {
      setSubmission("error");
    }
  }

  if (ticket.handoff) {
    return (
      <div className="handoff-result" role="status" tabIndex={-1} ref={result}>
        <Check size={17} />
        <div><strong>Follow-up assigned to {ticket.handoff.owner}</strong>
          <p>Support ticket {ticket.id} stays open.</p></div>
      </div>
    );
  }

  return (
    <form className="handoff-form" onSubmit={confirm} noValidate aria-busy={pending}>
      <label htmlFor="handoff-owner">Solutions engineer</label>
      <select
        id="handoff-owner"
        value={owner}
        disabled={pending}
        onChange={(event) => {
          const selectedOwner = owners.find((name) => name === event.target.value);
          setOwner(selectedOwner ?? "");
          setSubmission("idle");
        }}
      >
        <option value="">Select an assignee</option>
        {owners.map((name) => <option key={name}>{name}</option>)}
      </select>
      <button className="action" type="submit" disabled={!owner || pending}>
        <span>{pending ? "Confirming…" : "Confirm handoff"}</span>
        <ArrowRight size={16} />
      </button>
      {submission === "error" && (
        <p className="error-note" role="alert">Could not confirm the handoff. Try again.</p>
      )}
    </form>
  );
}

function highlightMessage(characters: string[], evidence: EvidenceSpan[]) {
  const spans: EvidenceSpan[] = [];
  for (const span of evidence.toSorted((a, b) => a.start - b.start)) {
    const last = spans.at(-1);
    if (last && span.start < last.end) {
      last.end = Math.max(last.end, span.end);
    } else {
      spans.push({ ...span });
    }
  }

  const segments: ReactNode[] = [];
  let cursor = 0;
  for (const { start, end } of spans) {
    segments.push(
      characters.slice(cursor, start).join(""),
      <mark key={start}>{characters.slice(start, end).join("")}</mark>,
    );
    cursor = end;
  }
  segments.push(characters.slice(cursor).join(""));
  return segments;
}

function formatWait(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  if (minutes <= 0) return `${rest}s`;
  return rest === 0 ? `${minutes}m` : `${minutes}m ${rest}s`;
}

function ReplyForm({ ticket, onUpdated }: {
  ticket: Ticket;
  onUpdated: (ticket: Ticket) => void;
}) {
  const [body, setBody] = useState("");
  const [submission, setSubmission] = useState<"idle" | "pending" | "error">("idle");
  const pending = submission === "pending";

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || !body.trim()) return;
    setSubmission("pending");
    try {
      onUpdated(await sendReply(ticket.id, body));
      setBody("");
      setSubmission("idle");
    } catch {
      setSubmission("error");
    }
  }

  return (
    <form className="reply-form" onSubmit={send}>
      <label htmlFor={"reply-" + ticket.id}>Reply to the customer</label>
      <textarea
        id={"reply-" + ticket.id}
        value={body}
        rows={3}
        disabled={pending}
        onChange={(event) => setBody(event.target.value)}
      />
      <button className="action" type="submit" disabled={pending || !body.trim()}>
        <span>{pending ? "Sending…" : "Send reply"}</span>
        <ArrowRight size={16} />
      </button>
      {submission === "error" && (
        <p className="error-note" role="alert">Could not send that reply. Try again.</p>
      )}
    </form>
  );
}

function TicketDetail({ ticket, onUpdated, headingRef }: {
  ticket: Ticket;
  onUpdated: (ticket: Ticket) => void;
  headingRef: Ref<HTMLHeadingElement>;
}) {
  const triage = ticket.triage;
  const isMixed = triage?.kind === "mixed";
  const isClarify = triage?.kind === "clarify";

  return (
    <article className="detail" aria-labelledby="ticket-heading">
      <section className="ticket-source" aria-labelledby="message-heading">
        <div className="ticket-meta">
          <span className="mono">{ticket.id}</span>
          <span className="separator" />
          <span>{ticket.customer}</span>
          <span className="open-label"><i />{ticket.status === "open" && "Support open"}</span>
        </div>
        <h2 id="ticket-heading" ref={headingRef} tabIndex={-1}>{ticket.title}</h2>
        <div className="conversation">
          {ticket.messages.map((message, index) => {
            const evidence = triage?.kind === "mixed" ? triage.evidence.filter((span) => span.message === index) : [];
            return (
              <div className="message" key={index}>
                <h3 className="eyebrow" id={index === 0 ? "message-heading" : undefined}>
                  {ticket.messages.length === 1 ? "Customer message" : `Customer message ${index + 1}`}
                </h3>
                <p>{triage && evidence.length > 0 ? highlightMessage(Array.from(message.body), evidence) : message.body}</p>
              </div>
            );
            })}
          {ticket.replies.map((reply, index) => (
            <div className="message" key={"reply-" + index}>
              <h3 className="eyebrow">{reply.author ?? "Relay Desk"}</h3>
              <p>{reply.body}</p>
            </div>
          ))}
        </div>
        {ticket.pending && (
          <p className="pending-note">
            <strong>{pendingLabels[ticket.pending.reason]}</strong>
            <span>Waiting {formatWait(ticket.pending.waiting_seconds)} since the customer's last message.</span>
          </p>
        )}
        <ReplyForm ticket={ticket} onUpdated={onUpdated} />
      </section>

      {triage && <section className="triage" aria-labelledby="triage-heading">
        <div className="triage-heading">
          <h3 id="triage-heading"><ScanLine size={17} /> Triage review</h3>
          <span className="mono">{ticket.origin === "live" ? "Live analysis" : "Sample assessment"}</span>
        </div>
        <p className="triage-summary">{triage.summary}</p>

        <div className="tracks">
          {(triage.support_steps.length > 0 || triage.kind === "support") && (
            <section className="track track-support" aria-labelledby="support-heading">
              <p className="track-tag"><Wrench size={15} /> Support track</p>
              <h4 id="support-heading">Technical support</h4>
              <ul className="track-list">
                {triage.support_steps.map((step) => <li key={step}>{step}</li>)}
              </ul>
              {triage.kind === "support" && (
                <p className="track-note"><Headset size={15} /> Continue in technical support.</p>
              )}
            </section>
          )}

          {isMixed && (
            <section className="track track-opportunity" aria-labelledby="opportunity-heading">
              <p className="track-tag"><Route size={15} /> Opportunity track</p>
              <h4 id="opportunity-heading">Commercial follow-up</h4>
              {triage.evidence.map(({ message, start, end }) => (
                <blockquote key={`${message}:${start}:${end}`}>
                  {Array.from(ticket.messages[message]?.body ?? "").slice(start, end).join("")}
                </blockquote>
              ))}
              {triage.questions.length > 0 && (
                <><p className="track-label">Questions for the handoff</p>
                <ul className="track-list">
                  {triage.questions.map((question) => <li key={question}>{question}</li>)}
                </ul></>
              )}
              <HandoffForm key={ticket.id} ticket={ticket} onUpdated={onUpdated} />
            </section>
          )}

          {isClarify && (
            <section className="track track-clarify" aria-labelledby="clarify-heading">
              <p className="track-tag"><CircleHelp size={15} /> Clarification track</p>
              <h4 id="clarify-heading">Questions to ask</h4>
              <ul className="track-list">
                {triage.questions.map((question) => <li key={question}>{question}</li>)}
              </ul>
              <p className="track-note">Ask for context before routing this request.</p>
            </section>
          )}
        </div>
      </section>}
    </article>
  );
}

function SignInForm({ onSignedIn }: { onSignedIn: () => void }) {
  const [token, setToken] = useState("");
  const [submission, setSubmission] = useState<"idle" | "pending" | "error">("idle");
  const pending = submission === "pending";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || !token.trim()) return;
    setSubmission("pending");
    try {
      await signIn(token.trim());
      onSignedIn();
    } catch {
      setSubmission("error");
    }
  }

  return (
    <form className="sign-in" onSubmit={submit}>
      <label htmlFor="support-token">Access token</label>
      <input
        id="support-token"
        type="password"
        autoComplete="current-password"
        value={token}
        disabled={pending}
        onChange={(event) => setToken(event.target.value)}
      />
      <button className="action" type="submit" disabled={pending || !token.trim()}>
        <span>{pending ? "Signing in…" : "Sign in"}</span>
        <ArrowRight size={16} />
      </button>
      {submission === "error" && (
        <p className="error-note" role="alert">That access token was not recognized.</p>
      )}
    </form>
  );
}

export default function InboxPage() {
  const [inbox, setInbox] = useState<InboxState>({ status: "loading" });
  const [selectedId, setSelectedId] = useState<string>();
  const [loadAttempt, setLoadAttempt] = useState(0);
  const ticketHeading = useRef<HTMLHeadingElement>(null);
  const addedTicket = useRef<string>(undefined);

  useEffect(() => {
    if (!supportToken()) {
      setInbox({ status: "signed-out" });
      return;
    }
    const controller = new AbortController();
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]);
    listTickets(signal).then(
      (tickets) => setInbox({ status: "ready", tickets, name: supportName() }),
      (error) => {
        if (controller.signal.aborted) return;
        setInbox(error instanceof SupportSignInRequired ? { status: "signed-out" } : { status: "error" });
      },
    );
    return () => controller.abort();
  }, [loadAttempt]);

  function updateTicket(updated: Ticket) {
    setInbox((current) => current.status === "ready"
      ? { ...current, tickets: current.tickets.map((ticket) => ticket.id === updated.id ? updated : ticket) }
      : current,
    );
  }

  function addTicket(ticket: Ticket) {
    setInbox((current) => current.status === "ready"
      ? { ...current, tickets: [...current.tickets, ticket] }
      : current,
    );
    addedTicket.current = ticket.id;
    setSelectedId(ticket.id);
  }

  useEffect(() => {
    if (addedTicket.current && addedTicket.current === selectedId) {
      addedTicket.current = undefined;
      ticketHeading.current?.focus();
    }
  }, [selectedId]);

  const tickets = inbox.status === "ready" ? inbox.tickets : [];
  const selected = tickets.find((ticket) => ticket.id === selectedId) ?? tickets[0];

  return (
    <DeskFrame section="RTC workspace">
      <main className="frame workspace">
        <div className="page-intro">
          <div>
            <p className="eyebrow"><Activity size={14} /> Support operations</p>
            <h1>Ticket inbox</h1>
            <p>Review RTC requests, continue troubleshooting, and route opportunities.</p>
            {inbox.status === "ready" && <p className="signed-in">Signed in as {inbox.name}.</p>}
          </div>
        </div>

        {inbox.status === "loading" && <div className="notice" role="status">Loading tickets…</div>}
        {inbox.status === "error" && (
          <div className="notice" role="alert">
            <strong>Ticket queue unavailable</strong>
            <p>Check that the API is running, then try again.</p>
            <button className="action" type="button" onClick={() => {
              setInbox({ status: "loading" });
              setLoadAttempt((attempt) => attempt + 1);
            }}>Retry loading tickets</button>
          </div>
        )}
        {inbox.status === "signed-out" && (
          <SignInForm onSignedIn={() => {
            setInbox({ status: "loading" });
            setLoadAttempt((attempt) => attempt + 1);
          }} />
        )}
        {inbox.status === "ready" && <NewLetterForm onCreated={addTicket} />}
        {inbox.status === "ready" && !selected && <p className="notice">No tickets in the queue.</p>}
        {selected && (
          <div className="workspace-grid">
            <TicketList tickets={tickets} selectedId={selected.id} onSelect={setSelectedId} />
            <TicketDetail ticket={selected} onUpdated={updateTicket} headingRef={ticketHeading} />
          </div>
        )}
      </main>
    </DeskFrame>
  );
}
