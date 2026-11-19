"use client";

import { ArrowRight, AudioLines } from "lucide-react";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { DeskFrame } from "../frame";
import {
  appendCustomerMessage, fetchCustomerTicket, LetterSubmissionError, openCustomerTicket,
  type CustomerTicket as CustomerRecord,
} from "../../lib/tickets";

type Submission =
  | { status: "idle" | "invalid" | "pending" }
  | { status: "error"; message: string };

function failure(error: unknown, fallback: string) {
  return error instanceof LetterSubmissionError
    ? "Could not save that message. Nothing new was added. Try again."
    : fallback;
}

export function OpenTicket() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [body, setBody] = useState("");
  const [submission, setSubmission] = useState<Submission>({ status: "idle" });
  const nameField = useRef<HTMLInputElement>(null);
  const messageField = useRef<HTMLTextAreaElement>(null);
  const pending = submission.status === "pending";
  const nameInvalid = submission.status === "invalid" && !name.trim();
  const messageInvalid = submission.status === "invalid" && !body.trim();

  async function openTicket(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    if (!name.trim() || !body.trim()) {
      setSubmission({ status: "invalid" });
      (name.trim() ? messageField : nameField).current?.focus();
      return;
    }

    setSubmission({ status: "pending" });
    try {
      const ticket = await openCustomerTicket({ customer: name.trim(), body });
      router.push("/customer/" + encodeURIComponent(ticket.id) + "/" + encodeURIComponent(ticket.credential));
    } catch (error) {
      setSubmission({
        status: "error",
        message: failure(error, "Could not open the ticket. Check this page before trying again."),
      });
    }
  }

  return (
    <DeskFrame section="Customer">
      <main className="frame workspace">
        <div className="page-intro">
          <p className="eyebrow">Customer</p>
          <h1>Open a ticket</h1>
          <p>Leave your name and your question. You can add another message on the same ticket. No account is needed.</p>
        </div>
        <section className="customer-panel">
          <form className="customer-form" onSubmit={openTicket} noValidate aria-busy={pending}>
            <label htmlFor="customer-name">Your name</label>
            <input
              id="customer-name" ref={nameField} value={name} required disabled={pending}
              autoComplete="name"
              aria-invalid={nameInvalid} aria-describedby={nameInvalid ? "customer-name-error" : undefined}
              onChange={(event) => setName(event.target.value)}
            />
            {nameInvalid && <p className="error-note" id="customer-name-error">Enter your name.</p>}
            <label htmlFor="customer-message">Your message</label>
            <textarea
              id="customer-message" ref={messageField} value={body} rows={5} required disabled={pending}
              aria-invalid={messageInvalid} aria-describedby={messageInvalid ? "customer-message-error" : undefined}
              onChange={(event) => setBody(event.target.value)}
            />
            {messageInvalid && <p className="error-note" id="customer-message-error">Write your message.</p>}
            <button className="action" type="submit" disabled={pending}>
              <span>{pending ? "Sending…" : "Open ticket"}</span>
              <ArrowRight size={16} />
            </button>
            {submission.status === "error" && <p className="error-note" role="alert">{submission.message}</p>}
          </form>
        </section>
      </main>
    </DeskFrame>
  );
}

type TicketView =
  | { status: "loading" }
  | { status: "missing" }
  | { status: "error" }
  | { status: "ready"; ticket: CustomerRecord };

const refreshDelayMs = 2000;

function sameConversation(current: CustomerRecord, next: CustomerRecord) {
  return current.title === next.title
    && current.messages.length === next.messages.length
    && current.replies.length === next.replies.length
    && current.messages.every((message, index) => message.body === next.messages[index]?.body)
    && current.replies.every((reply, index) =>
      reply.body === next.replies[index]?.body && reply.author === next.replies[index]?.author);
}

function olderThan(current: CustomerRecord, next: CustomerRecord) {
  return next.messages.length < current.messages.length || next.replies.length < current.replies.length;
}

function sentAt(value: string | null | undefined) {
  if (!value) return null;
  const time = Date.parse(value);
  return Number.isNaN(time) ? null : time;
}

type ThreadTurn = {
  key: string;
  role: "customer" | "desk";
  body: string;
  author: string | null;
  at: number | null;
  index: number;
};

function threadTurns(ticket: CustomerRecord): ThreadTurn[] {
  const turns: ThreadTurn[] = [
    ...ticket.messages.map((message, index) => ({
      key: "message-" + index,
      role: "customer" as const,
      body: message.body,
      author: null,
      at: sentAt(message.spoken_at),
      index,
    })),
    ...ticket.replies.map((reply, index) => ({
      key: "reply-" + index,
      role: "desk" as const,
      body: reply.body,
      author: reply.author,
      at: sentAt(reply.sent_at),
      index,
    })),
  ];
  return turns.sort((left, right) => {
    if (left.at !== null && right.at !== null && left.at !== right.at) return left.at - right.at;
    if (left.at !== null && right.at === null) return -1;
    if (left.at === null && right.at !== null) return 1;
    if (left.role !== right.role) return left.role === "customer" ? -1 : 1;
    return left.index - right.index;
  });
}

export function CustomerTicket({ ticketId, credential }: { ticketId: string; credential: string }) {
  const [view, setView] = useState<TicketView>({ status: "loading" });
  const [body, setBody] = useState("");
  const [submission, setSubmission] = useState<Submission>({ status: "idle" });
  const [loadAttempt, setLoadAttempt] = useState(0);
  const messageField = useRef<HTMLTextAreaElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const pending = submission.status === "pending";
  const messageInvalid = submission.status === "invalid" && !body.trim();

  useEffect(() => {
    const controller = new AbortController();
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]);
    fetchCustomerTicket(ticketId, credential, signal).then(
      (ticket) => setView(ticket ? { status: "ready", ticket } : { status: "missing" }),
      () => {
        if (!controller.signal.aborted) setView({ status: "error" });
      },
    );
    return () => controller.abort();
  }, [ticketId, credential, loadAttempt]);

  useEffect(() => {
    if (view.status !== "ready") return;
    let stopped = false;
    let timer = 0;

    async function refresh() {
      if (stopped || document.visibilityState === "hidden") return;
      try {
        const ticket = await fetchCustomerTicket(ticketId, credential, AbortSignal.timeout(8000));
        if (stopped || !ticket) return;
        setView((current) => {
          if (current.status !== "ready" || olderThan(current.ticket, ticket) || sameConversation(current.ticket, ticket)) {
            return current;
          }
          return { status: "ready", ticket };
        });
      } catch {
        // A missed refresh leaves the conversation already on screen.
      }
    }

    function schedule() {
      timer = window.setTimeout(() => {
        void refresh().finally(() => {
          if (!stopped) schedule();
        });
      }, refreshDelayMs);
    }

    function onVisible() {
      if (document.visibilityState !== "visible") return;
      window.clearTimeout(timer);
      void refresh().finally(() => {
        if (!stopped) schedule();
      });
    }

    schedule();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [ticketId, credential, view.status]);

  useEffect(() => {
    const thread = threadRef.current;
    if (thread) thread.scrollTop = thread.scrollHeight;
  }, [view]);

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || view.status !== "ready") return;
    if (!body.trim()) {
      setSubmission({ status: "invalid" });
      messageField.current?.focus();
      return;
    }

    setSubmission({ status: "pending" });
    try {
      const ticket = await appendCustomerMessage(view.ticket.id, view.ticket.credential, body);
      setBody("");
      setSubmission({ status: "idle" });
      setView({ status: "ready", ticket });
    } catch (error) {
      setSubmission({
        status: "error",
        message: failure(error, "Could not add this message. Check the conversation before trying again."),
      });
    }
  }

  const ticket = view.status === "ready" ? view.ticket : undefined;

  return (
    <main className="customer-shell">
      <header className="customer-head">
        <div className="customer-measure">
          <div className="brand">
            <span className="brand-icon"><AudioLines size={18} /></span>
            <strong>Relay Desk</strong>
            <span className="brand-divider" />
            <span className="brand-section">Customer</span>
          </div>
          <h1>{ticket ? ticket.title : "Your ticket"}</h1>
          {ticket && (
            <p className="customer-meta">
              <span className="mono">{ticket.id}</span>
              <span className="separator" />
              <span>{ticket.customer}</span>
              <span className="separator" />
              <span>Your name is only shown on this ticket.</span>
            </p>
          )}
        </div>
      </header>

      <div className="customer-thread" ref={threadRef}>
        <div className="customer-measure customer-log" aria-label="Conversation">
          {view.status === "loading" && <p className="customer-status" role="status">Loading your ticket…</p>}
          {view.status === "missing" && <p className="customer-status">This ticket is not open.</p>}
          {view.status === "error" && (
            <div className="customer-status" role="alert">
              <strong>Ticket unavailable</strong>
              <p>Check that the desk is running, then try again.</p>
              <button className="action" type="button" onClick={() => {
                setView({ status: "loading" });
                setLoadAttempt((attempt) => attempt + 1);
              }}>Retry loading ticket</button>
            </div>
          )}
          {ticket && threadTurns(ticket).map((turn) => (
            turn.role === "customer" ? (
              <div className="message customer" key={turn.key}>
                <p>{turn.body}</p>
              </div>
            ) : (
              <div className="message desk" key={turn.key}>
                <span className="customer-author">{turn.author ?? "Relay Desk"}</span>
                <p>{turn.body}</p>
              </div>
            )
          ))}
        </div>
      </div>

      {ticket && (
        <form className="customer-dock" onSubmit={send} noValidate aria-busy={pending}>
          <div className="customer-measure">
            <div className="customer-compose">
              <label className="visually-hidden" htmlFor="follow-up">Add a message</label>
              <textarea
                id="follow-up" ref={messageField} value={body} rows={1} required disabled={pending}
                placeholder="Add a message"
                aria-invalid={messageInvalid} aria-describedby={messageInvalid ? "follow-up-error" : undefined}
                onChange={(event) => setBody(event.target.value)}
              />
              <button className="customer-send" type="submit" disabled={pending} aria-label={pending ? "Sending…" : "Send message"}>
                <ArrowRight size={18} />
              </button>
            </div>
            {messageInvalid && <p className="error-note" id="follow-up-error">Write your message.</p>}
            {submission.status === "error" && <p className="error-note" role="alert">{submission.message}</p>}
          </div>
        </form>
      )}
    </main>
  );
}
