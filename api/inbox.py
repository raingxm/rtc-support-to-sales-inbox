import asyncio
import re
import secrets
from collections.abc import Collection
from datetime import datetime, timezone
from threading import Lock
from typing import Annotated, Literal, NamedTuple, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

Owner = Literal["Maya Chen", "Jordan Lee"]
STOPPED_WAITING = "stopped-waiting"
DOCUMENTATION_UNOPENED = "documentation-unopened"
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


class NotAuthenticated(Exception):
    pass


class SupportPerson(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str = Field(min_length=1)


class HandoffRejected(Exception):
    pass


class WithdrawalRejected(Exception):
    pass


class SolutionEngineerRejected(Exception):
    pass


class HandbackRejected(Exception):
    pass


class Span(BaseModel):
    """Half-open Unicode code point offsets into one customer message."""

    model_config = ConfigDict(frozen=True)
    message: int = Field(default=0, ge=0)
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


class CustomerMessage(BaseModel):
    model_config = ConfigDict(frozen=True)
    body: str
    spoken_at: datetime | None = None

    @model_validator(mode="after")
    def check_content(self) -> "CustomerMessage":
        if not self.body.strip():
            raise ValueError("A customer message is required.")
        return self


class Reply(BaseModel):
    model_config = ConfigDict(frozen=True)
    body: str
    author: str | None = None

    @model_validator(mode="after")
    def check_body(self) -> "Reply":
        if not self.body.strip():
            raise ValueError("A reply is required.")
        return self


class DocumentationPage(BaseModel):
    """One sentence copied from an opened documentation page, with that page's address."""

    model_config = ConfigDict(frozen=True)
    url: str = Field(min_length=1)
    quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def check_content(self) -> "DocumentationPage":
        if not self.url.strip() or not self.quote.strip():
            raise ValueError("An opened page needs an address and a sentence.")
        return self


PendingReason = Literal["stopped-waiting", "documentation-unopened"]


class Pending(BaseModel):
    """Support-only waiting state. The customer entrance never receives this."""

    model_config = ConfigDict(frozen=True)
    reason: PendingReason
    waiting_seconds: int = Field(ge=0)


class CustomerView(BaseModel):
    """What the customer entrance shows: the conversation, never pending work."""

    model_config = ConfigDict(frozen=True)
    id: str
    customer: str
    title: str
    messages: tuple[CustomerMessage, ...]
    replies: tuple[Reply, ...] = ()


class TicketContent(BaseModel):
    model_config = ConfigDict(frozen=True)
    title: str = Field(min_length=1)
    customer: str = Field(min_length=1)
    messages: tuple[CustomerMessage, ...] = Field(min_length=1)
    triage: Triage | None = None
    credential: str = ""
    replies: tuple[Reply, ...] = ()
    pending_reason: PendingReason | None = None
    taken_over: bool = False
    handed_back_by: str | None = None

    @model_validator(mode="before")
    @classmethod
    def letter_body_is_one_message(cls, data: object) -> object:
        if isinstance(data, dict) and "messages" not in data and "body" in data:
            return {**data, "messages": [{"body": data["body"]}]}
        return data

    @model_validator(mode="after")
    def check_evidence_bounds(self) -> "TicketContent":
        if isinstance(self.triage, MixedTriage):
            for span in self.triage.evidence:
                if span.message >= len(self.messages):
                    raise ValueError("Evidence span does not match a customer message.")
                quote_text(self.messages[span.message].body, span)
        return self


class Ticket(TicketContent):
    id: str
    origin: Literal["sample", "live"]
    status: Literal["open"] = "open"
    handoff: Handoff | None = None
    confirmed_by: str | None = None
    withdrawn_by: str | None = None
    pending: Pending | None = None

    def assign_handoff(self, owner: Owner, confirmed_by: str) -> "Ticket":
        if not isinstance(self.triage, MixedTriage):
            raise HandoffRejected
        if self.handoff is not None:
            return self
        return self.model_copy(update={
            "handoff": Handoff(owner=owner),
            "confirmed_by": confirmed_by,
            "withdrawn_by": None,
        })

    def withdraw_handoff(self, withdrawn_by: str) -> "Ticket":
        if self.handoff is None:
            raise WithdrawalRejected
        return self.model_copy(update={"handoff": None, "withdrawn_by": withdrawn_by})

    def hand_back(self, handed_back_by: str) -> "Ticket":
        if not self.taken_over:
            raise HandbackRejected
        return self.model_copy(update={"taken_over": False, "handed_back_by": handed_back_by})


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


class _Documents(Protocol):
    async def open(self, body: str) -> DocumentationPage | None: ...


class _Settled(NamedTuple):
    draft: _Draft
    triage: Triage
    page: DocumentationPage | None


class _Clock(Protocol):
    def now(self) -> datetime: ...


def quote_text(body: str, span: Span) -> str:
    if span.end > len(body):
        raise ValueError("Evidence span extends beyond the original letter.")
    return body[span.start : span.end]


def _signed_in(person: SupportPerson | None) -> SupportPerson:
    if person is None or not person.name.strip():
        raise NotAuthenticated
    return person


def _quoted_reply(page: DocumentationPage) -> Reply:
    return Reply(body=f"{page.quote}\n{page.url}")


def _cannot_answer(messages: Sequence[CustomerMessage]) -> str:
    latest = messages[-1].body if messages else ""
    if any("\u4e00" <= character <= "\u9fff" for character in latest):
        return "这次答不了。"
    return "I can't answer this."


def _provisional_title(body: str) -> str:
    line = next((line.strip() for line in body.splitlines() if line.strip()), "Ticket")
    return line[:80]


def _same_credential(stored: str, offered: str) -> bool:
    if not stored or not offered:
        return False
    return secrets.compare_digest(stored, offered)


_CREDENTIAL = re.compile(
    r"""(?x)
    [`"']?
    (?i:UserSig|SDKSecretKey)
    [`"']?
    [ \t]*[=:：][ \t]*
    (?:
        (?: "[^"\n]*" | '[^'\n]*' | `[^`\n]*` | \S+ ) [ \t]*\n?
        | \n[ \t]*\S+[ \t]*(?:\n|$)
    )
    """
)


def _transcript(messages: Sequence[CustomerMessage]) -> str:
    bodies = [_CREDENTIAL.sub("", message.body) for message in messages]
    if len(bodies) == 1:
        return bodies[0]
    return "\n\n".join(bodies)


def _locate(messages: Sequence[CustomerMessage], quote: str) -> Span:
    if not quote:
        raise QuoteRejected(quote, "empty-quote")
    for index, message in enumerate(messages):
        start = message.body.find(quote)
        if start >= 0:
            return Span(message=index, start=start, end=start + len(quote))
    raise QuoteRejected(quote, "not-in-letter")


def _check(messages: Sequence[CustomerMessage], draft: _Draft) -> Triage:
    seen: set[str] = set()
    spans: list[Span] = []
    for quote in draft.evidence:
        if quote in seen:
            raise QuoteRejected(quote, "duplicate-quote")
        spans.append(_locate(messages, quote))
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
    def append_message(self, ticket_id: str, message: CustomerMessage) -> Ticket: ...
    def drop_last_message(self, ticket_id: str, message_count: int) -> Ticket: ...
    def confirm_handoff(self, ticket_id: str, owner: Owner, confirmed_by: str) -> Ticket: ...
    def withdraw_handoff(self, ticket_id: str, withdrawn_by: str) -> Ticket: ...
    def hand_back(self, ticket_id: str, handed_back_by: str) -> Ticket: ...
    def delete(self, ticket_id: str) -> None: ...
    def apply_analysis(self, ticket_id: str, triage: Triage, title: str, message_count: int) -> Ticket: ...
    def mark_stopped_waiting(self, ticket_id: str, message_count: int, reply_count: int) -> Ticket: ...
    def land_analysis(
        self,
        ticket_id: str,
        message_count: int,
        reply_count: int,
        triage: Triage,
        title: str,
        reply: Reply | None,
        pending_reason: PendingReason | None,
    ) -> Ticket: ...
    def add_reply(self, ticket_id: str, reply: Reply) -> Ticket: ...


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

    def append_message(self, ticket_id: str, message: CustomerMessage) -> Ticket:
        with self._lock:
            latest = self._tickets.get(ticket_id)
            if latest is None:
                raise TicketNotFound(ticket_id)
            updated = latest.model_copy(update={"messages": (*latest.messages, message)})
            self._tickets[ticket_id] = updated
            return updated

    def drop_last_message(self, ticket_id: str, message_count: int) -> Ticket:
        with self._lock:
            latest = self._tickets.get(ticket_id)
            if latest is None:
                raise TicketNotFound(ticket_id)
            if len(latest.messages) == message_count:
                latest = latest.model_copy(update={"messages": latest.messages[:-1]})
                self._tickets[ticket_id] = latest
            return latest

    def confirm_handoff(self, ticket_id: str, owner: Owner, confirmed_by: str) -> Ticket:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                raise TicketNotFound(ticket_id)
            updated = ticket.assign_handoff(owner, confirmed_by)
            self._tickets[ticket_id] = updated
            return updated

    def withdraw_handoff(self, ticket_id: str, withdrawn_by: str) -> Ticket:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                raise TicketNotFound(ticket_id)
            updated = ticket.withdraw_handoff(withdrawn_by)
            self._tickets[ticket_id] = updated
            return updated

    def delete(self, ticket_id: str) -> None:
        with self._lock:
            self._tickets.pop(ticket_id, None)

    def apply_analysis(self, ticket_id: str, triage: Triage, title: str, message_count: int) -> Ticket:
        with self._lock:
            latest = self._tickets.get(ticket_id)
            if latest is None:
                raise TicketNotFound(ticket_id)
            if latest.handoff is None and len(latest.messages) == message_count:
                latest = latest.model_copy(update={"triage": triage, "title": title, "pending_reason": None})
                self._tickets[ticket_id] = latest
            return latest

    def mark_stopped_waiting(self, ticket_id: str, message_count: int, reply_count: int) -> Ticket:
        with self._lock:
            latest = self._tickets.get(ticket_id)
            if latest is None:
                raise TicketNotFound(ticket_id)
            if len(latest.messages) == message_count and len(latest.replies) == reply_count:
                latest = latest.model_copy(update={"pending_reason": STOPPED_WAITING})
                self._tickets[ticket_id] = latest
            return latest

    def land_analysis(
        self,
        ticket_id: str,
        message_count: int,
        reply_count: int,
        triage: Triage,
        title: str,
        reply: Reply | None,
        pending_reason: PendingReason | None,
    ) -> Ticket:
        with self._lock:
            latest = self._tickets.get(ticket_id)
            if latest is None:
                raise TicketNotFound(ticket_id)
            if len(latest.messages) != message_count:
                return latest
            spoken = any(reply.author for reply in latest.replies)
            update: dict[str, object] = {}
            if latest.handoff is None and not spoken:
                update["triage"] = triage
                update["title"] = title
            if reply is not None and not spoken and len(latest.replies) == reply_count:
                update["replies"] = (*latest.replies, reply)
                update["pending_reason"] = pending_reason
            if not update:
                return latest
            updated = latest.model_copy(update=update)
            self._tickets[ticket_id] = updated
            return updated

    def add_reply(self, ticket_id: str, reply: Reply) -> Ticket:
        with self._lock:
            latest = self._tickets.get(ticket_id)
            if latest is None:
                raise TicketNotFound(ticket_id)
            updated = latest.model_copy(update={
                "replies": (*latest.replies, reply),
                "pending_reason": None,
                "taken_over": True,
            })
            self._tickets[ticket_id] = updated
            return updated

    def hand_back(self, ticket_id: str, handed_back_by: str) -> Ticket:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                raise TicketNotFound(ticket_id)
            updated = ticket.hand_back(handed_back_by)
            self._tickets[ticket_id] = updated
            return updated


class Inbox:
    def __init__(
        self,
        analyzer: _Analyzer | None = None,
        *,
        store: TicketStore | None = None,
        documents: _Documents | None = None,
        clock: _Clock | None = None,
        wait_limit: float = 30,
        support_names: Collection[str] = (),
    ) -> None:
        self._analyzer = analyzer
        self._store = store if store is not None else _MemoryTicketStore()
        self._documents = documents
        self._clock = clock
        self._wait_limit = wait_limit
        self._support_names = frozenset(name.strip() for name in support_names if name.strip())
        self._background: set[asyncio.Task[None]] = set()

    def _now(self) -> datetime:
        return self._clock.now() if self._clock is not None else datetime.now(timezone.utc)

    def _present(self, ticket: Ticket) -> Ticket:
        if ticket.pending_reason is None:
            return ticket
        spoken_at = next(
            (message.spoken_at for message in reversed(ticket.messages) if message.spoken_at is not None),
            None,
        )
        elapsed = 0 if spoken_at is None else int((self._now() - spoken_at).total_seconds())
        return ticket.model_copy(update={
            "pending": Pending(reason=ticket.pending_reason, waiting_seconds=max(0, elapsed)),
        })

    async def _draft(self, messages: Sequence[CustomerMessage]) -> _Draft:
        analyzer = self._analyzer
        if analyzer is None:
            raise AnalysisUnavailable
        return await analyzer.draft(_transcript(messages))

    def _track(self, task: asyncio.Task[None]) -> None:
        self._background.add(task)

        def done(finished: asyncio.Task[None]) -> None:
            self._background.discard(finished)
            if not finished.cancelled():
                finished.exception()

        task.add_done_callback(done)

    async def _attempt(self, messages: Sequence[CustomerMessage]) -> _Settled:
        draft = await self._draft(messages)
        triage = _check(messages, draft)
        page = None
        if self._documents is not None:
            page = await self._documents.open(_transcript(messages))
        return _Settled(draft, triage, page)

    async def _stop(self, ticket_id: str, message_count: int, reply_count: int) -> Ticket:
        stopped = await asyncio.to_thread(
            self._store.mark_stopped_waiting, ticket_id, message_count, reply_count,
        )
        return self._present(stopped)

    def _documented_reply(
        self,
        messages: Sequence[CustomerMessage],
        settled: _Settled,
    ) -> tuple[Reply, PendingReason | None] | None:
        if settled.page is None:
            if self._documents is None:
                return None
            return Reply(body=_cannot_answer(messages)), DOCUMENTATION_UNOPENED
        return _quoted_reply(settled.page), None

    async def _publish_ready(
        self,
        ticket_id: str,
        messages: Sequence[CustomerMessage],
        reply_count: int,
        settled: _Settled,
    ) -> Ticket:
        message_count = len(messages)
        documented = self._documented_reply(messages, settled)
        if documented is None:
            return self._present(await asyncio.to_thread(
                self._store.apply_analysis, ticket_id, settled.triage, settled.draft.title, message_count,
            ))
        reply, pending_reason = documented
        return self._present(await asyncio.to_thread(
            self._store.land_analysis,
            ticket_id,
            message_count,
            reply_count,
            settled.triage,
            settled.draft.title,
            reply,
            pending_reason,
        ))

    async def _land_late(
        self,
        attempt: asyncio.Task[_Settled],
        ticket_id: str,
        message_count: int,
        reply_count: int,
    ) -> None:
        try:
            settled = await attempt
        except (TimeoutError, AnalysisFailed, AnalysisUnavailable, QuoteRejected):
            return
        reply = None if settled.page is None else _quoted_reply(settled.page)
        await asyncio.to_thread(
            self._store.land_analysis,
            ticket_id,
            message_count,
            reply_count,
            settled.triage,
            settled.draft.title,
            reply,
            None,
        )

    async def _resolve(self, ticket_id: str, messages: Sequence[CustomerMessage], reply_count: int) -> Ticket:
        message_count = len(messages)
        attempt = asyncio.create_task(self._attempt(messages))
        try:
            settled = await asyncio.wait_for(asyncio.shield(attempt), self._wait_limit)
        except AnalysisFailed:
            attempt.exception()
            return await self._stop(ticket_id, message_count, reply_count)
        except TimeoutError:
            if not attempt.done():
                stopped = await self._stop(ticket_id, message_count, reply_count)
                self._track(asyncio.create_task(
                    self._land_late(attempt, ticket_id, message_count, reply_count),
                ))
                return stopped
            error = attempt.exception()
            if error is None:
                settled = attempt.result()
            elif isinstance(error, (TimeoutError, AnalysisFailed)):
                return await self._stop(ticket_id, message_count, reply_count)
            else:
                raise error
        return await self._publish_ready(ticket_id, messages, reply_count, settled)

    @classmethod
    def open(
        cls,
        samples: Sequence[_SampleRecord],
        analyzer: _Analyzer | None = None,
        *,
        store: TicketStore | None = None,
        documents: _Documents | None = None,
        clock: _Clock | None = None,
        wait_limit: float = 30,
        support_names: Collection[str] = (),
    ) -> "Inbox":
        inbox = cls(
            analyzer,
            store=store,
            documents=documents,
            clock=clock,
            wait_limit=wait_limit,
            support_names=support_names,
        )
        tickets = []
        for sample in samples:
            messages = (CustomerMessage(body=sample.body),)
            draft = _Draft(title=sample.title, **sample.triage.model_dump())
            tickets.append(Ticket(
                id=sample.id,
                title=sample.title,
                customer=sample.customer,
                messages=messages,
                origin="sample",
                credential=secrets.token_urlsafe(32),
                triage=_check(messages, draft),
            ))
        inbox._store.seed(tickets)
        return inbox

    def list_tickets(self, person: SupportPerson | None = None) -> list[Ticket]:
        _signed_in(person)
        return [self._present(ticket) for ticket in self._store.list_tickets()]

    def get(self, ticket_id: str, person: SupportPerson | None = None) -> Ticket | None:
        _signed_in(person)
        ticket = self._store.get(ticket_id)
        return None if ticket is None else self._present(ticket)

    async def submit(self, letter: Letter) -> Ticket:
        if self._analyzer is None:
            raise AnalysisUnavailable
        messages = (CustomerMessage(body=letter.body, spoken_at=self._now()),)
        ticket = await asyncio.to_thread(self._store.append, TicketContent(
            title=_provisional_title(letter.body),
            customer=letter.customer,
            messages=messages,
            credential=secrets.token_urlsafe(32),
        ))
        try:
            return await self._resolve(ticket.id, messages, len(ticket.replies))
        except QuoteRejected:
            await asyncio.to_thread(self._store.delete, ticket.id)
            raise

    def open_customer(self, ticket_id: str, credential: str) -> CustomerView:
        ticket = self._store.get(ticket_id)
        if ticket is None or not _same_credential(ticket.credential, credential):
            raise TicketNotFound(ticket_id)
        return CustomerView(
            id=ticket.id,
            customer=ticket.customer,
            title=ticket.title,
            messages=ticket.messages,
            replies=ticket.replies,
        )

    async def append_customer_message(self, ticket_id: str, body: str, *, credential: str) -> Ticket:
        message = CustomerMessage(body=body, spoken_at=self._now())
        current = await asyncio.to_thread(self._store.get, ticket_id)
        if current is None or not _same_credential(current.credential, credential):
            raise TicketNotFound(ticket_id)
        if current.handoff is None and self._analyzer is None:
            raise AnalysisUnavailable
        prior_count = len(current.messages)
        saved = await asyncio.to_thread(self._store.append_message, ticket_id, message)
        if current.handoff is not None:
            return self._present(saved)
        try:
            return await self._resolve(ticket_id, saved.messages, len(saved.replies))
        except QuoteRejected:
            await asyncio.to_thread(self._store.drop_last_message, ticket_id, prior_count + 1)
            raise

    def use_support_names(self, names: Collection[str]) -> None:
        self._support_names = frozenset(name.strip() for name in names if name.strip())

    def confirm_handoff(self, ticket_id: str, owner: Owner, *, person: SupportPerson | None = None) -> Ticket:
        person = _signed_in(person)
        if owner == person.name or owner in self._support_names:
            raise SolutionEngineerRejected
        return self._present(self._store.confirm_handoff(ticket_id, owner, person.name))

    def withdraw_handoff(self, ticket_id: str, *, person: SupportPerson | None = None) -> Ticket:
        person = _signed_in(person)
        return self._present(self._store.withdraw_handoff(ticket_id, person.name))

    def hand_back(self, ticket_id: str, *, person: SupportPerson | None = None) -> Ticket:
        person = _signed_in(person)
        return self._present(self._store.hand_back(ticket_id, person.name))

    def reply(self, ticket_id: str, body: str, *, person: SupportPerson) -> Ticket:
        reply = Reply(body=body, author=person.name)
        return self._present(self._store.add_reply(ticket_id, reply))


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
