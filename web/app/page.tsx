"use client";

import {
  Activity, ArrowRight, Check, ChevronRight, CircleHelp,
  Headset, Inbox, Route, ScanLine, Wrench,
} from "lucide-react";
import { type FormEvent, type ReactNode, type Ref, useEffect, useRef, useState } from "react";
import { DeskFrame } from "./frame";
import {
  createHandoff, fetchTicket, handBack as requestHandBack, LetterSubmissionError, listTickets, owners,
  ReplyContextChanged, sendReply, signIn, submitLetter,
  withdrawHandoff,
  supportName, supportToken, SupportSignInRequired, type EvidenceSpan, type Owner, type Ticket,
} from "../lib/tickets";

const kindLabels = {
  mixed: "Opportunity",
  support: "Support only",
  clarify: "Needs context",
};

const pendingLabels = {
  "stopped-waiting": "Stopped waiting",
  "documentation-unopened": "No documentation page",
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
                  : ticket.withdrawn_by
                    ? "Handoff withdrawn"
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
  const engineers = owners.filter((name) => name !== supportName());
  const [owner, setOwner] = useState<Owner | "">("");
  const [submission, setSubmission] = useState<"idle" | "pending" | "error">("idle");
  const result = useRef<HTMLDivElement>(null);
  const shouldFocus = useRef(false);
  const pending = submission === "pending";

  useEffect(() => {
    if (!shouldFocus.current || (!ticket.handoff && !ticket.withdrawn_by)) return;
    shouldFocus.current = false;
    result.current?.focus();
  }, [ticket.handoff, ticket.withdrawn_by, ticket.confirmed_by]);

  async function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!owner || pending) return;

    shouldFocus.current = true;
    setSubmission("pending");
    try {
      onUpdated(await createHandoff(ticket.id, owner));
      setSubmission("idle");
    } catch {
      shouldFocus.current = false;
      setSubmission("error");
    }
  }

  async function withdraw() {
    if (pending) return;
    shouldFocus.current = true;
    setSubmission("pending");
    try {
      onUpdated(await withdrawHandoff(ticket.id));
      setOwner("");
      setSubmission("idle");
    } catch {
      shouldFocus.current = false;
      setSubmission("error");
    }
  }

  if (ticket.handoff) {
    return (
      <div className="handoff-result" role="status" tabIndex={-1} ref={result}>
        <Check size={17} />
        <div>
          <strong>Follow-up assigned to {ticket.handoff.owner}</strong>
          {ticket.confirmed_by && <p>Confirmed by {ticket.confirmed_by}</p>}
          <p>Support ticket {ticket.id} stays open.</p>
        </div>
        <button className="action" type="button" onClick={withdraw} disabled={pending}>
          {pending ? "Withdrawing…" : "Withdraw handoff"}
        </button>
        {submission === "error" && (
          <p className="error-note" role="alert">Could not withdraw the handoff. Try again.</p>
        )}
      </div>
    );
  }

  return (
    <>
      {ticket.withdrawn_by && (
        <div className="handoff-result" role="status" tabIndex={-1} ref={result}>
          <div>
            {ticket.confirmed_by && <strong>Confirmed by {ticket.confirmed_by}</strong>}
            <p>Withdrawn by {ticket.withdrawn_by}</p>
          </div>
        </div>
      )}
      <form className="handoff-form" onSubmit={confirm} noValidate aria-busy={pending}>
        <label htmlFor="handoff-owner">Solutions engineer</label>
        <select
          id="handoff-owner"
          value={owner}
          disabled={pending}
          onChange={(event) => {
            const selectedOwner = engineers.find((name) => name === event.target.value);
            setOwner(selectedOwner ?? "");
            setSubmission("idle");
          }}
        >
          <option value="">Select an assignee</option>
          {engineers.map((name) => <option key={name}>{name}</option>)}
        </select>
        <button className="action" type="submit" disabled={!owner || pending}>
          <span>{pending ? "Confirming…" : "Confirm handoff"}</span>
          <ArrowRight size={16} />
        </button>
        {submission === "error" && (
          <p className="error-note" role="alert">Could not confirm the handoff. Try again.</p>
        )}
      </form>
    </>
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

function Takeover({ ticket, onUpdated }: {
  ticket: Ticket;
  onUpdated: (ticket: Ticket) => void;
}) {
  const [submission, setSubmission] = useState<"idle" | "pending" | "error">("idle");
  const pending = submission === "pending";
  if (!ticket.taken_over && !ticket.handed_back_by) return null;

  async function handBack() {
    if (pending) return;
    setSubmission("pending");
    try {
      onUpdated(await requestHandBack(ticket.id));
      setSubmission("idle");
    } catch {
      setSubmission("error");
    }
  }

  return (
    <div className="takeover-note" role="status">
      {ticket.taken_over
        ? <strong>With support</strong>
        : <strong>Handed back by {ticket.handed_back_by}</strong>}
      {ticket.taken_over && (
        <button className="action" type="button" onClick={handBack} disabled={pending}>
          {pending ? "Handing back…" : "Hand back"}
        </button>
      )}
      {submission === "error" && (
        <p className="error-note" role="alert">Could not hand this back. Try again.</p>
      )}
    </div>
  );
}

function ReplyForm({ ticket, onUpdated }: {
  ticket: Ticket;
  onUpdated: (ticket: Ticket) => void;
}) {
  const revision = ticket.reply_revision;
  const [edit, setEdit] = useState<{ revision: number; body: string }>();
  const [conflictRevision, setConflictRevision] = useState<number>();
  const [submission, setSubmission] = useState<"idle" | "pending" | "error">("idle");
  const pending = submission === "pending";
  const waitingForRefresh = conflictRevision === revision;
  const discarded = conflictRevision !== undefined || (edit !== undefined && edit.revision !== revision);
  const body = waitingForRefresh ? "" : (edit?.revision === revision ? edit.body : ticket.reply_draft ?? "");
  const fieldId = "reply-" + ticket.id;

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || waitingForRefresh || !body.trim()) return;
    setSubmission("pending");
    try {
      onUpdated(await sendReply(ticket.id, body, revision));
      setEdit(undefined);
      setConflictRevision(undefined);
      setSubmission("idle");
    } catch (error) {
      if (error instanceof ReplyContextChanged) {
        setConflictRevision(revision);
        setSubmission("idle");
      } else {
        setSubmission("error");
      }
    }
  }

  return (
    <form className="reply-form" onSubmit={send}>
      <label htmlFor={fieldId}>Reply to the customer</label>
      {ticket.reply_draft && !waitingForRefresh && (
        <p className="reply-draft-note" id={fieldId + "-draft"}>Suggested draft · Only visible to support</p>
      )}
      <textarea
        id={fieldId}
        aria-describedby={ticket.reply_draft && !waitingForRefresh ? fieldId + "-draft" : undefined}
        value={body}
        rows={3}
        disabled={pending || waitingForRefresh}
        onChange={(event) => {
          setEdit({ revision, body: event.target.value });
          setConflictRevision(undefined);
          setSubmission("idle");
        }}
      />
      <button className="action" type="submit" disabled={pending || waitingForRefresh || !body.trim()}>
        <span>{pending ? "Sending…" : "Send reply"}</span>
        <ArrowRight size={16} />
      </button>
      {discarded && (
        <p className="reply-draft-note" role="status">
          {waitingForRefresh
            ? "The conversation changed. Waiting for the latest messages."
            : "The conversation changed. Review the latest messages before replying."}
        </p>
      )}
      {submission === "error" && !discarded && (
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
        <Takeover ticket={ticket} onUpdated={onUpdated} />
        <ReplyForm key={ticket.id} ticket={ticket} onUpdated={onUpdated} />
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

function withUpdatedTicket(inbox: InboxState, updated: Ticket): InboxState {
  if (inbox.status !== "ready") return inbox;
  return {
    ...inbox,
    tickets: inbox.tickets.map((ticket) =>
      ticket.id === updated.id && ticket.reply_revision <= updated.reply_revision ? updated : ticket,
    ),
  };
}

export default function InboxPage() {
  const [inbox, setInbox] = useState<InboxState>({ status: "loading" });
  const [selectedId, setSelectedId] = useState<string>();
  const [loadAttempt, setLoadAttempt] = useState(0);
  const ticketHeading = useRef<HTMLHeadingElement>(null);
  const addedTicket = useRef<string>(undefined);
  const ticketWrites = useRef(0);

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
    ticketWrites.current++;
    setInbox((current) => withUpdatedTicket(current, updated));
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

  const openTicketId = selected?.id;

  useEffect(() => {
    if (!openTicketId) return;
    const ticketId = openTicketId;
    const controller = new AbortController();
    let timer = 0;

    async function refresh() {
      const writes = ticketWrites.current;
      try {
        if (document.visibilityState === "hidden") return;
        const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]);
        const updated = await fetchTicket(ticketId, signal);
        if (controller.signal.aborted || writes !== ticketWrites.current || !updated) return;
        setInbox((current) => withUpdatedTicket(current, updated));
      } catch (error) {
        if (!controller.signal.aborted && error instanceof SupportSignInRequired) {
          setInbox({ status: "signed-out" });
        }
      } finally {
        if (!controller.signal.aborted) timer = window.setTimeout(refresh, 1500);
      }
    }

    void refresh();
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [openTicketId]);

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
