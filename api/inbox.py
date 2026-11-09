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


class Ticket(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    title: str = Field(min_length=1)
    customer: str = Field(min_length=1)
    body: str
    origin: Literal["sample", "live"]
    status: Literal["open"] = "open"
    triage: Triage
    handoff: Handoff | None = None

    @model_validator(mode="after")
    def check_evidence_bounds(self) -> "Ticket":
        if isinstance(self.triage, MixedTriage):
            for span in self.triage.evidence:
                quote_text(self.body, span)
        return self


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


class Inbox:
    def __init__(self, analyzer: _Analyzer | None = None) -> None:
        self._analyzer = analyzer
        self._tickets: dict[str, Ticket] = {}

    @classmethod
    def open(cls, samples: Sequence[_SampleRecord], analyzer: _Analyzer | None = None) -> "Inbox":
        inbox = cls(analyzer)
        for sample in samples:
            draft = _Draft(title=sample.title, **sample.triage.model_dump())
            inbox._tickets[sample.id] = Ticket(
                id=sample.id,
                title=sample.title,
                customer=sample.customer,
                body=sample.body,
                origin="sample",
                triage=_check(sample.body, draft),
            )
        return inbox

    def list_tickets(self) -> list[Ticket]:
        return list(self._tickets.values())

    def get(self, ticket_id: str) -> Ticket | None:
        return self._tickets.get(ticket_id)

    async def submit(self, letter: Letter) -> Ticket:
        if self._analyzer is None:
            raise AnalysisUnavailable
        draft = await self._analyzer.draft(letter.body)
        triage = _check(letter.body, draft)
        suffix = max((int(ticket_id.removeprefix("RTC-")) for ticket_id in self._tickets), default=1042)
        ticket = Ticket(
            id=f"RTC-{suffix + 1}",
            title=draft.title,
            customer=letter.customer,
            body=letter.body,
            origin="live",
            triage=triage,
        )
        self._tickets[ticket.id] = ticket
        return ticket

    def confirm_handoff(self, ticket_id: str, owner: Owner) -> Ticket:
        ticket = self.get(ticket_id)
        if ticket is None:
            raise TicketNotFound(ticket_id)
        if not isinstance(ticket.triage, MixedTriage):
            raise HandoffRejected
        if ticket.handoff is not None:
            return ticket
        updated = ticket.model_copy(update={"handoff": Handoff(owner=owner)})
        self._tickets[ticket_id] = updated
        return updated


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
