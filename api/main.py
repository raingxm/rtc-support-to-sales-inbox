import asyncio
import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from api.inbox import (
    AnalysisFailed,
    AnalysisUnavailable,
    Handoff,
    HandoffRejected,
    Inbox,
    Letter,
    QuoteRejected,
    SAMPLES,
    Ticket,
    TicketNotFound,
)
from api.model_analyzer import configured_analyzer
from api.postgres import PostgresTicketStore


def _configured_inbox() -> Inbox:
    database_url = os.getenv("DATABASE_URL", "").strip()
    store = PostgresTicketStore(database_url) if database_url else None
    return Inbox.open(SAMPLES, analyzer=configured_analyzer(), store=store)


def _request_inbox(request: Request) -> Inbox:
    return request.app.state.inbox


InboxDependency = Annotated[Inbox, Depends(_request_inbox)]


def create_app(inbox: Inbox | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.inbox = inbox if inbox is not None else await asyncio.to_thread(_configured_inbox)
        yield

    app = FastAPI(title="RTC Support-to-Sales Inbox", lifespan=lifespan)

    @app.exception_handler(QuoteRejected)
    async def reject_quote(_request: Request, error: QuoteRejected) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": error.reason, "quote": error.quote})

    @app.get("/tickets")
    def list_tickets(active_inbox: InboxDependency) -> list[Ticket]:
        return active_inbox.list_tickets()

    @app.post("/tickets", status_code=201)
    async def submit_letter(letter: Letter, active_inbox: InboxDependency) -> Ticket:
        try:
            return await active_inbox.submit(letter)
        except AnalysisUnavailable:
            raise HTTPException(status_code=503, detail="Letter analysis is not configured.") from None
        except AnalysisFailed:
            raise HTTPException(status_code=502, detail="The model could not analyze this letter.") from None

    @app.post("/tickets/{ticket_id}/handoff")
    def confirm_handoff(ticket_id: str, handoff: Handoff, active_inbox: InboxDependency) -> Ticket:
        try:
            return active_inbox.confirm_handoff(ticket_id, handoff.owner)
        except TicketNotFound:
            raise HTTPException(status_code=404, detail="Ticket not found.") from None
        except HandoffRejected:
            raise HTTPException(
                status_code=409, detail="This ticket does not have a handoff recommendation."
            ) from None

    return app


app = create_app()
