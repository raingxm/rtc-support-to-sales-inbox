import asyncio
from threading import Lock
from typing import Annotated, Literal, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

Owner = Literal["Maya Chen", "Jordan Lee"]
QuoteFailure = Literal[
    "not-in-letter",
    "empty-quote",
    "duplicate-quote",
    "mixed-without-evidence",
    "evidence-on-non-mixed",
]


class AnalysisUnavailable(Exception):
    pass


class AnalysisFailed(Exception):
    pass


class QuoteRejected(Exception):
    def __init__(self, quote: str, reason: QuoteFailure) -> None:
        self.quote = quote
        self.reason = reason
        super().__init__(reason)


class TicketNotFound(Exception):
    pass


class HandoffRejected(Exception):
    pass


class Span(BaseModel):
    """Half-open Unicode code point offsets into the original body."""

    model_config = ConfigDict(frozen=True)
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def check_order(self) -> "Span":
        if self.end <= self.start:
            raise ValueError("An evidence span must be nonempty.")
        return self


class _TriageText(BaseModel):
    model_config = ConfigDict(frozen=True)
    summary: str
    support_steps: tuple[str, ...]
    questions: tuple[str, ...]


class MixedTriage(_TriageText):
    kind: Literal["mixed"]
    evidence: tuple[Span, ...] = Field(min_length=1)


class OtherTriage(_TriageText):
    kind: Literal["support", "clarify"]


Triage = Annotated[MixedTriage | OtherTriage, Field(discriminator="kind")]


class Handoff(BaseModel):
    model_config = ConfigDict(frozen=True)
    owner: Owner


class Letter(BaseModel):
    model_config = ConfigDict(frozen=True)
    customer: str
    body: str

    @model_validator(mode="after")
    def check_content(self) -> "Letter":
        if not self.customer.strip() or not self.body.strip():
            raise ValueError("Customer and letter are required.")
        return self


class TicketContent(BaseModel):
    model_config = ConfigDict(frozen=True)
    title: str = Field(min_length=1)
    customer: str = Field(min_length=1)
    body: str
    triage: Triage

    @model_validator(mode="after")
    def check_evidence_bounds(self) -> "TicketContent":
        if isinstance(self.triage, MixedTriage):
            for span in self.triage.evidence:
                quote_text(self.body, span)
        return self


class Ticket(TicketContent):
    id: str
    origin: Literal["sample", "live"]
    status: Literal["open"] = "open"
    handoff: Handoff | None = None

    def assign_handoff(self, owner: Owner) -> "Ticket":
        if not isinstance(self.triage, MixedTriage):
            raise HandoffRejected
        if self.handoff is not None:
            return self
        return self.model_copy(update={"handoff": Handoff(owner=owner)})


class _SampleTriage(_TriageText):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["mixed", "support", "clarify"]
    evidence: tuple[str, ...]


class _SampleRecord(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    title: str
    customer: str
    body: str
    triage: _SampleTriage


class _Draft(_SampleTriage):
    title: str = Field(min_length=1)


class _Analyzer(Protocol):
    async def draft(self, body: str) -> _Draft: ...


def quote_text(body: str, span: Span) -> str:
    if span.end > len(body):
        raise ValueError("Evidence span extends beyond the original letter.")
    return body[span.start : span.end]


def _locate(body: str, quote: str) -> Span:
    if not quote:
        raise QuoteRejected(quote, "empty-quote")
    start = body.find(quote)
    if start < 0:
        raise QuoteRejected(quote, "not-in-letter")
    return Span(start=start, end=start + len(quote))


def _check(body: str, draft: _Draft) -> Triage:
    seen: set[str] = set()
    spans: list[Span] = []
    for quote in draft.evidence:
        if quote in seen:
            raise QuoteRejected(quote, "duplicate-quote")
        spans.append(_locate(body, quote))
        seen.add(quote)

    if draft.kind == "mixed":
        if not spans:
            raise QuoteRejected("", "mixed-without-evidence")
        return MixedTriage(
            kind="mixed",
            summary=draft.summary,
            support_steps=draft.support_steps,
            questions=draft.questions,
            evidence=tuple(spans),
        )
    if spans:
        raise QuoteRejected(draft.evidence[0], "evidence-on-non-mixed")
    return OtherTriage(
        kind=draft.kind,
        summary=draft.summary,
        support_steps=draft.support_steps,
        questions=draft.questions,
    )


class TicketStore(Protocol):
    def seed(self, samples: Sequence[Ticket]) -> None: ...
    def list_tickets(self) -> list[Ticket]: ...
    def get(self, ticket_id: str) -> Ticket | None: ...
    def append(self, content: TicketContent) -> Ticket: ...
    def confirm_handoff(self, ticket_id: str, owner: Owner) -> Ticket: ...


class _MemoryTicketStore:
    def __init__(self) -> None:
        self._tickets: dict[str, Ticket] = {}
        self._lock = Lock()

    def seed(self, samples: Sequence[Ticket]) -> None:
        with self._lock:
            for sample in samples:
                self._tickets.setdefault(sample.id, sample)

    def list_tickets(self) -> list[Ticket]:
        with self._lock:
            return list(self._tickets.values())

    def get(self, ticket_id: str) -> Ticket | None:
        with self._lock:
            return self._tickets.get(ticket_id)

    def append(self, content: TicketContent) -> Ticket:
        with self._lock:
            suffix = max((int(ticket_id.removeprefix("RTC-")) for ticket_id in self._tickets), default=1042)
            ticket = Ticket(id=f"RTC-{suffix + 1}", origin="live", **content.model_dump())
            self._tickets[ticket.id] = ticket
            return ticket

    def confirm_handoff(self, ticket_id: str, owner: Owner) -> Ticket:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                raise TicketNotFound(ticket_id)
            updated = ticket.assign_handoff(owner)
            self._tickets[ticket_id] = updated
            return updated


class Inbox:
    def __init__(self, analyzer: _Analyzer | None = None, *, store: TicketStore | None = None) -> None:
        self._analyzer = analyzer
        self._store = store if store is not None else _MemoryTicketStore()

    @classmethod
    def open(
        cls,
        samples: Sequence[_SampleRecord],
        analyzer: _Analyzer | None = None,
        *,
        store: TicketStore | None = None,
    ) -> "Inbox":
        inbox = cls(analyzer, store=store)
        tickets = []
        for sample in samples:
            draft = _Draft(title=sample.title, **sample.triage.model_dump())
            tickets.append(Ticket(
                id=sample.id,
                title=sample.title,
                customer=sample.customer,
                body=sample.body,
                origin="sample",
                triage=_check(sample.body, draft),
            ))
        inbox._store.seed(tickets)
        return inbox

    def list_tickets(self) -> list[Ticket]:
        return self._store.list_tickets()

    def get(self, ticket_id: str) -> Ticket | None:
        return self._store.get(ticket_id)

    async def submit(self, letter: Letter) -> Ticket:
        if self._analyzer is None:
            raise AnalysisUnavailable
        draft = await self._analyzer.draft(letter.body)
        content = TicketContent(
            title=draft.title,
            customer=letter.customer,
            body=letter.body,
            triage=_check(letter.body, draft),
        )
        return await asyncio.to_thread(self._store.append, content)

    def confirm_handoff(self, ticket_id: str, owner: Owner) -> Ticket:
        return self._store.confirm_handoff(ticket_id, owner)


SAMPLES = (
    _SampleRecord(
        id="RTC-1042",
        title="Intermittent recording failures and a migration pilot",
        customer="Harborline Labs",
        body=(
            "Recordings occasionally fail in our web calls. "
            "We’re evaluating a move from Twilio Video and want to launch a pilot next month."
        ),
        triage=_SampleTriage(
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
    _SampleRecord(
        id="RTC-1041",
        title="Invalid token when joining a room in Flutter",
        customer="Northwind Studio",
        body=(
            "How do I join a room in the Flutter SDK? "
            "My join call returns an invalid token error."
        ),
        triage=_SampleTriage(
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
    _SampleRecord(
        id="RTC-1040",
        title="Cloud recording availability",
        customer="Cedarline Media",
        body="Do you support cloud recording?",
        triage=_SampleTriage(
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
