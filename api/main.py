from fastapi import FastAPI, HTTPException, Request
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


def create_app(inbox: Inbox) -> FastAPI:
    app = FastAPI(title="RTC Support-to-Sales Inbox")

    @app.exception_handler(QuoteRejected)
    async def reject_quote(_request: Request, error: QuoteRejected) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": error.reason, "quote": error.quote})

    @app.get("/tickets")
    async def list_tickets() -> list[Ticket]:
        return inbox.list_tickets()

    @app.post("/tickets", status_code=201)
    async def submit_letter(letter: Letter) -> Ticket:
        try:
            return await inbox.submit(letter)
        except AnalysisUnavailable:
            raise HTTPException(status_code=503, detail="Letter analysis is not configured.") from None
        except AnalysisFailed:
            raise HTTPException(status_code=502, detail="The model could not analyze this letter.") from None

    @app.post("/tickets/{ticket_id}/handoff")
    async def confirm_handoff(ticket_id: str, handoff: Handoff) -> Ticket:
        try:
            return inbox.confirm_handoff(ticket_id, handoff.owner)
        except TicketNotFound:
            raise HTTPException(status_code=404, detail="Ticket not found.") from None
        except HandoffRejected:
            raise HTTPException(
                status_code=409, detail="This ticket does not have a handoff recommendation."
            ) from None

    return app


app = create_app(Inbox.open(SAMPLES, analyzer=configured_analyzer()))
