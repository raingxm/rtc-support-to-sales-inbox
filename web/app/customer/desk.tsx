"use client";

import { ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { DeskFrame } from "../frame";
import {
  appendCustomerMessage, fetchTicket, LetterSubmissionError, submitLetter, type Ticket,
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
      const ticket = await submitLetter({ customer: name.trim(), body });
      router.push("/customer/" + encodeURIComponent(ticket.id));
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
  | { status: "ready"; ticket: Ticket };

export function CustomerTicket({ ticketId }: { ticketId: string }) {
  const [view, setView] = useState<TicketView>({ status: "loading" });
  const [body, setBody] = useState("");
  const [submission, setSubmission] = useState<Submission>({ status: "idle" });
  const [loadAttempt, setLoadAttempt] = useState(0);
  const messageField = useRef<HTMLTextAreaElement>(null);
  const pending = submission.status === "pending";
  const messageInvalid = submission.status === "invalid" && !body.trim();

  useEffect(() => {
    const controller = new AbortController();
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]);
    fetchTicket(ticketId, signal).then(
      (ticket) => setView(ticket ? { status: "ready", ticket } : { status: "missing" }),
      () => {
        if (!controller.signal.aborted) setView({ status: "error" });
      },
    );
    return () => controller.abort();
  }, [ticketId, loadAttempt]);

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
      const ticket = await appendCustomerMessage(view.ticket.id, body);
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
    <DeskFrame section="Customer">
      <main className="frame workspace">
        <div className="page-intro">
          <p className="eyebrow">Customer</p>
          <h1>{ticket ? ticket.title : "Your ticket"}</h1>
          {ticket && (
            <p className="ticket-meta">
              <span className="mono">{ticket.id}</span>
              <span className="separator" />
              <span>{ticket.customer}</span>
              <span>Your name is only shown on this ticket.</span>
            </p>
          )}
        </div>

        {view.status === "loading" && <div className="notice" role="status">Loading your ticket…</div>}
        {view.status === "missing" && <p className="notice">This ticket is not open.</p>}
        {view.status === "error" && (
          <div className="notice" role="alert">
            <strong>Ticket unavailable</strong>
            <p>Check that the desk is running, then try again.</p>
            <button className="action" type="button" onClick={() => {
              setView({ status: "loading" });
              setLoadAttempt((attempt) => attempt + 1);
            }}>Retry loading ticket</button>
          </div>
        )}

        {ticket && (
          <section className="customer-panel" aria-labelledby="conversation-heading">
            <h2 className="eyebrow" id="conversation-heading">Conversation</h2>
            <div className="conversation">
              {ticket.messages.map((message, index) => (
                <div className="message" key={index}>
                  <h3 className="eyebrow">{ticket.messages.length === 1 ? "Your message" : `Message ${index + 1}`}</h3>
                  <p>{message.body}</p>
                </div>
              ))}
            </div>
            <form className="customer-form" onSubmit={send} noValidate aria-busy={pending}>
              <label htmlFor="follow-up">Add a message</label>
              <textarea
                id="follow-up" ref={messageField} value={body} rows={4} required disabled={pending}
                aria-invalid={messageInvalid} aria-describedby={messageInvalid ? "follow-up-error" : undefined}
                onChange={(event) => setBody(event.target.value)}
              />
              {messageInvalid && <p className="error-note" id="follow-up-error">Write your message.</p>}
              <button className="action" type="submit" disabled={pending}>
                <span>{pending ? "Sending…" : "Send message"}</span>
                <ArrowRight size={16} />
              </button>
              {submission.status === "error" && <p className="error-note" role="alert">{submission.message}</p>}
            </form>
          </section>
        )}
      </main>
    </DeskFrame>
  );
}
