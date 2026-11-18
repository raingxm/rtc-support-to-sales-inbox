import asyncio
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from api.inbox import (
    AnalysisFailed,
    AnalysisUnavailable,
    CustomerMessage,
    CustomerView,
    HandbackRejected,
    Handoff,
    HandoffRejected,
    Inbox,
    Letter,
    QuoteRejected,
    Reply,
    SAMPLES,
    SolutionEngineerRejected,
    SupportPerson,
    Ticket,
    TicketNotFound,
    WithdrawalRejected,
)
from api.model_analyzer import configured_analyzer
from api.postgres import PostgresTicketStore

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def load_local_env(path: Path | None = None) -> None:
    load_dotenv(_ENV_FILE if path is None else path, override=False)


class CustomerEntrance(BaseModel):
    id: str
    credential: str
    customer: str
    title: str
    messages: tuple[CustomerMessage, ...]
    replies: tuple[Reply, ...]


class MessageBody(BaseModel):
    body: str


class ReplyBody(BaseModel):
    body: str


class SignIn(BaseModel):
    token: str


def load_staff(raw: str | None = None) -> dict[str, SupportPerson]:
    staff: dict[str, SupportPerson] = {}
    source = os.getenv("RTC_SUPPORT_STAFF", "") if raw is None else raw
    for item in source.split(","):
        name, separator, token = item.partition("=")
        name, token = name.strip(), token.strip()
        if separator and name and token:
            staff[token] = SupportPerson(name=name)
    return staff


def _person_for(staff: dict[str, SupportPerson], token: str) -> SupportPerson | None:
    match = None
    for stored, person in staff.items():
        if secrets.compare_digest(stored, token):
            match = person
    return match


def _configured_inbox() -> Inbox:
    load_local_env()
    database_url = os.getenv("DATABASE_URL", "").strip()
    store = PostgresTicketStore(database_url) if database_url else None
    return Inbox.open(SAMPLES, analyzer=configured_analyzer(), store=store)


def _request_inbox(request: Request) -> Inbox:
    return request.app.state.inbox


def _support_person(request: Request) -> SupportPerson:
    header = request.headers.get("authorization", "")
    token = header.removeprefix("Bearer ").strip() if header.lower().startswith("bearer ") else ""
    person = _person_for(request.app.state.staff, token) if token else None
    if person is None:
        raise HTTPException(status_code=401, detail="Sign in as support.")
    return person


InboxDependency = Annotated[Inbox, Depends(_request_inbox)]
SupportDependency = Annotated[SupportPerson, Depends(_support_person)]


def _entrance(view: CustomerView, credential: str) -> CustomerEntrance:
    return CustomerEntrance(credential=credential, **view.model_dump())


def _entrance_from_ticket(ticket: Ticket) -> CustomerEntrance:
    return CustomerEntrance(
        id=ticket.id,
        credential=ticket.credential,
        customer=ticket.customer,
        title=ticket.title,
        messages=ticket.messages,
        replies=ticket.replies,
    )


def create_app(
    inbox: Inbox | None = None,
    *,
    staff: dict[str, SupportPerson] | None = None,
) -> FastAPI:
    load_local_env()
    configured_staff = load_staff() if staff is None else staff

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.staff = configured_staff
        opened = inbox if inbox is not None else await asyncio.to_thread(_configured_inbox)
        opened.use_support_names(person.name for person in configured_staff.values())
        app.state.inbox = opened
        yield

    app = FastAPI(title="RTC Support-to-Sales Inbox", lifespan=lifespan)

    @app.exception_handler(QuoteRejected)
    async def reject_quote(_request: Request, error: QuoteRejected) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": error.reason, "quote": error.quote})

    @app.post("/session")
    def start_session(sign_in: SignIn, request: Request) -> SupportPerson:
        person = _person_for(request.app.state.staff, sign_in.token)
        if person is None:
            raise HTTPException(status_code=401, detail="That sign-in was not recognized.")
        return person

    @app.get("/tickets")
    def list_tickets(person: SupportDependency, active_inbox: InboxDependency) -> list[Ticket]:
        return active_inbox.list_tickets(person)

    @app.post("/tickets", status_code=201)
    async def submit_letter(
        letter: Letter,
        _person: SupportDependency,
        active_inbox: InboxDependency,
    ) -> Ticket:
        try:
            return await active_inbox.submit(letter)
        except AnalysisUnavailable:
            raise HTTPException(status_code=503, detail="Letter analysis is not configured.") from None
        except AnalysisFailed:
            raise HTTPException(status_code=502, detail="The model could not analyze this letter.") from None

    @app.get("/tickets/{ticket_id}")
    def read_ticket(ticket_id: str, person: SupportDependency, active_inbox: InboxDependency) -> Ticket:
        ticket = active_inbox.get(ticket_id, person)
        if ticket is None:
            raise HTTPException(status_code=404, detail="Ticket not found.")
        return ticket

    @app.post("/tickets/{ticket_id}/handoff")
    def confirm_handoff(
        ticket_id: str,
        handoff: Handoff,
        person: SupportDependency,
        active_inbox: InboxDependency,
    ) -> Ticket:
        try:
            return active_inbox.confirm_handoff(ticket_id, handoff.owner, person=person)
        except TicketNotFound:
            raise HTTPException(status_code=404, detail="Ticket not found.") from None
        except HandoffRejected:
            raise HTTPException(
                status_code=409, detail="This ticket does not have a handoff recommendation."
            ) from None
        except SolutionEngineerRejected:
            raise HTTPException(
                status_code=409, detail="A support person cannot be the solutions engineer."
            ) from None

    @app.post("/tickets/{ticket_id}/withdrawal")
    def withdraw_handoff(
        ticket_id: str,
        person: SupportDependency,
        active_inbox: InboxDependency,
    ) -> Ticket:
        try:
            return active_inbox.withdraw_handoff(ticket_id, person=person)
        except TicketNotFound:
            raise HTTPException(status_code=404, detail="Ticket not found.") from None
        except WithdrawalRejected:
            raise HTTPException(status_code=409, detail="There is no handoff to withdraw.") from None

    @app.post("/tickets/{ticket_id}/handback")
    def hand_back(
        ticket_id: str,
        person: SupportDependency,
        active_inbox: InboxDependency,
    ) -> Ticket:
        try:
            return active_inbox.hand_back(ticket_id, person=person)
        except TicketNotFound:
            raise HTTPException(status_code=404, detail="Ticket not found.") from None
        except HandbackRejected:
            raise HTTPException(status_code=409, detail="Support has not taken over this ticket.") from None

    @app.post("/tickets/{ticket_id}/replies")
    def send_reply(
        ticket_id: str,
        reply: ReplyBody,
        person: SupportDependency,
        active_inbox: InboxDependency,
    ) -> Ticket:
        try:
            return active_inbox.reply(ticket_id, reply.body, person=person)
        except TicketNotFound:
            raise HTTPException(status_code=404, detail="Ticket not found.") from None
        except ValidationError:
            raise HTTPException(status_code=422, detail="Write a reply.") from None

    @app.post("/customer-tickets", status_code=201)
    async def open_customer_ticket(letter: Letter, active_inbox: InboxDependency) -> CustomerEntrance:
        try:
            return _entrance_from_ticket(await active_inbox.submit(letter))
        except AnalysisUnavailable:
            raise HTTPException(status_code=503, detail="Letter analysis is not configured.") from None
        except AnalysisFailed:
            raise HTTPException(status_code=502, detail="The model could not analyze this letter.") from None

    @app.get("/customer-tickets/{ticket_id}/{credential}")
    def read_customer_ticket(
        ticket_id: str,
        credential: str,
        active_inbox: InboxDependency,
    ) -> CustomerEntrance:
        try:
            return _entrance(active_inbox.open_customer(ticket_id, credential), credential)
        except TicketNotFound:
            raise HTTPException(status_code=404, detail="Ticket not found.") from None

    @app.post("/customer-tickets/{ticket_id}/{credential}/messages")
    async def append_customer_message(
        ticket_id: str,
        credential: str,
        message: MessageBody,
        active_inbox: InboxDependency,
    ) -> CustomerEntrance:
        try:
            ticket = await active_inbox.append_customer_message(
                ticket_id, message.body, credential=credential,
            )
        except TicketNotFound:
            raise HTTPException(status_code=404, detail="Ticket not found.") from None
        except ValidationError:
            raise HTTPException(status_code=422, detail="Write a message.") from None
        except AnalysisUnavailable:
            raise HTTPException(status_code=503, detail="Letter analysis is not configured.") from None
        except AnalysisFailed:
            raise HTTPException(status_code=502, detail="The model could not analyze this letter.") from None
        return _entrance_from_ticket(ticket)

    return app


app = create_app()
