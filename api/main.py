from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

Owner = Literal["Maya Chen", "Jordan Lee"]


class Handoff(BaseModel):
    owner: Owner


class Triage(BaseModel):
    kind: Literal["mixed", "support", "clarify"]
    summary: str
    support_steps: list[str]
    evidence: list[str]
    questions: list[str]


class Ticket(BaseModel):
    id: str
    title: str
    customer: str
    body: str
    status: Literal["open"] = "open"
    triage: Triage
    handoff: Handoff | None = None


app = FastAPI(title="RTC Support-to-Sales Inbox")

tickets = {
    ticket.id: ticket
    for ticket in (
        Ticket(
            id="RTC-1042",
            title="Intermittent recording failures and a migration pilot",
            customer="Harborline Labs",
            body=(
                "Recordings occasionally fail in our web calls. "
                "We’re evaluating a move from Twilio Video and want to launch a pilot next month."
            ),
            triage=Triage(
                kind="mixed",
                summary=(
                    "Keep investigating the recording failures and route the migration pilot "
                    "to a solutions engineer."
                ),
                support_steps=[
                    "Ask for the failure time and time zone.",
                    "Request the affected call or recording ID.",
                ],
                evidence=[
                    "evaluating a move from Twilio Video",
                    "launch a pilot next month",
                ],
                questions=[
                    "How many concurrent calls do you expect during the pilot?",
                    "How do you need recordings to be delivered?",
                ],
            ),
        ),
        Ticket(
            id="RTC-1041",
            title="Invalid token when joining a room in Flutter",
            customer="Northwind Studio",
            body=(
                "How do I join a room in the Flutter SDK? "
                "My join call returns an invalid token error."
            ),
            triage=Triage(
                kind="support",
                summary="Troubleshoot Flutter room authentication.",
                support_steps=[
                    "Confirm the Flutter SDK version and the exact error code.",
                    "Check the token expiry and whether its identity and room match the join request.",
                ],
                evidence=[],
                questions=[],
            ),
        ),
        Ticket(
            id="RTC-1040",
            title="Cloud recording availability",
            customer="Cedarline Media",
            body="Do you support cloud recording?",
            triage=Triage(
                kind="clarify",
                summary="Ask about the recording use case before deciding on a handoff.",
                support_steps=["Confirm what the customer needs to record."],
                evidence=[],
                questions=[
                    "What kind of calls or streams do you need to record?",
                    "Do you have a planned launch date?",
                ],
            ),
        ),
    )
}


@app.get("/tickets")
async def list_tickets() -> list[Ticket]:
    return list(tickets.values())


@app.post("/tickets/{ticket_id}/handoff")
async def confirm_handoff(ticket_id: str, handoff: Handoff) -> Ticket:
    ticket = tickets.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    if ticket.triage.kind != "mixed":
        raise HTTPException(
            status_code=409, detail="This ticket does not have a handoff recommendation."
        )
    if ticket.handoff is not None:
        return ticket

    # No await between reading and replacing a ticket in the single demo process.
    updated = ticket.model_copy(update={"handoff": handoff})
    tickets[ticket_id] = updated
    return updated
