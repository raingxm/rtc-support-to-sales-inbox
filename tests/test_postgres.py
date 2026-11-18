import asyncio
import os
from datetime import datetime, timedelta, timezone
from threading import Barrier
from unittest import IsolatedAsyncioTestCase, skipUnless
from uuid import uuid4

from psycopg import connect, sql
from psycopg.conninfo import make_conninfo

from api.inbox import (
    HandoffRejected, Inbox, Letter, Owner, QuoteRejected, SAMPLES, SupportPerson, TicketNotFound, _Draft,
)
from api.postgres import PostgresTicketStore


_TEST_DATABASE_URL = os.getenv("RTC_TEST_DATABASE_URL")
_PILOT = "We want to launch a pilot next month."
_SUPPORT = SupportPerson(name="Riley Cho")


class FixedAnalyzer:
    async def draft(self, body: str) -> _Draft:
        return _Draft(
            title="Recording issue and pilot",
            kind="mixed",
            summary="Troubleshoot recording and follow up on the pilot.",
            support_steps=["Ask for the call ID."],
            questions=[],
            evidence=[_PILOT],
        )


@skipUnless(_TEST_DATABASE_URL, "set RTC_TEST_DATABASE_URL to run against PostgreSQL")
class PostgresInboxTest(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.schema = sql.Identifier(f"rtc_test_{uuid4().hex}")
        with connect(_TEST_DATABASE_URL) as connection:
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(self.schema))
        self.addCleanup(self.drop_test_schema)
        self.dsn = make_conninfo(_TEST_DATABASE_URL, options=f"-c search_path={self.schema.as_string()}")

    def drop_test_schema(self) -> None:
        with connect(_TEST_DATABASE_URL) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(self.schema))

    def open_inbox(self) -> Inbox:
        return Inbox.open(SAMPLES, analyzer=FixedAnalyzer(), store=PostgresTicketStore(self.dsn))

    async def test_reopening_keeps_the_ticket_and_first_handoff(self) -> None:
        inbox = self.open_inbox()
        body = "📹 Recording failed. " + _PILOT
        ticket = await inbox.submit(Letter(customer="Cypress Video", body=body))
        self.assertEqual(ticket.id, "RTC-1043")
        assigned = inbox.confirm_handoff(ticket.id, "Maya Chen", person=_SUPPORT)
        sample_assigned = inbox.confirm_handoff("RTC-1042", "Jordan Lee", person=_SUPPORT)

        reopened = self.open_inbox()
        self.assertEqual([item.id for item in reopened.list_tickets(_SUPPORT)], [
            "RTC-1042", "RTC-1041", "RTC-1040", "RTC-1043",
        ])
        self.assertEqual(reopened.get(ticket.id, _SUPPORT), assigned)
        self.assertEqual(reopened.get("RTC-1042", _SUPPORT), sample_assigned)
        self.assertEqual(
            reopened.confirm_handoff(ticket.id, "Jordan Lee", person=_SUPPORT).handoff.owner,
            "Maya Chen",
        )

        with self.assertRaises(HandoffRejected):
            reopened.confirm_handoff("RTC-1041", "Maya Chen", person=_SUPPORT)
        with self.assertRaises(TicketNotFound):
            reopened.confirm_handoff("RTC-01043", "Maya Chen", person=_SUPPORT)
        with self.assertRaises(QuoteRejected):
            await reopened.submit(Letter(customer="Cypress Video", body="Recording failed."))
        self.assertEqual(len(reopened.list_tickets(_SUPPORT)), 4)

    async def test_reopening_keeps_a_later_customer_message(self) -> None:
        inbox = self.open_inbox()
        ticket = await inbox.submit(Letter(customer="Cypress Video", body=_PILOT))
        updated = await inbox.append_customer_message(
            ticket.id, "The recordings are still failing.", credential=ticket.credential,
        )

        reopened = self.open_inbox()
        stored = reopened.get(ticket.id, _SUPPORT)
        self.assertEqual(stored, updated)
        self.assertEqual([message.body for message in stored.messages], [
            _PILOT,
            "The recordings are still failing.",
        ])
        self.assertEqual(stored.triage.kind, "mixed")

    async def test_concurrent_confirmations_store_one_owner(self) -> None:
        first_inbox = self.open_inbox()
        second_inbox = self.open_inbox()
        ticket = await first_inbox.submit(Letter(customer="Cypress Video", body=_PILOT))
        start = Barrier(2)

        def confirm(inbox: Inbox, owner: Owner):
            start.wait(timeout=5)
            return inbox.confirm_handoff(ticket.id, owner, person=_SUPPORT).handoff

        first, second = await asyncio.gather(
            asyncio.to_thread(confirm, first_inbox, "Maya Chen"),
            asyncio.to_thread(confirm, second_inbox, "Jordan Lee"),
        )
        self.assertIsNotNone(first)
        self.assertEqual(first, second)
        with connect(self.dsn) as connection:
            rows = connection.execute("SELECT ticket_number, owner FROM rtc_handoffs").fetchall()
        self.assertEqual(rows, [(1043, first.owner)])

    async def test_reopening_keeps_a_timed_out_ticket_its_wait_and_a_signed_reply(self) -> None:
        class Hanging:
            async def draft(self, body: str) -> _Draft:
                await asyncio.Event().wait()
                raise AssertionError("unreachable")

        clock = _Clock()
        inbox = Inbox.open(
            SAMPLES, analyzer=Hanging(), store=PostgresTicketStore(self.dsn), clock=clock, wait_limit=0.05,
        )
        body = "Recording failed and nobody answered."
        ticket = await inbox.submit(Letter(customer="Cypress Video", body=body))
        clock.advance(120)

        reopened = Inbox.open(
            SAMPLES, analyzer=Hanging(), store=PostgresTicketStore(self.dsn), clock=clock, wait_limit=0.05,
        )
        support = reopened.get(ticket.id, _SUPPORT)
        self.assertIsNotNone(support)
        assert support is not None and support.pending is not None
        self.assertEqual(support.id, ticket.id)
        self.assertEqual([message.body for message in support.messages], [body])
        self.assertEqual(support.pending.reason, "已经停止等待")
        self.assertEqual(support.pending.waiting_seconds, 120)
        customer = reopened.open_customer(ticket.id, ticket.credential)
        self.assertEqual([message.body for message in customer.messages], [body])
        self.assertEqual(customer.replies, ())
        self.assertNotIn("pending", customer.model_dump())

        reopened.reply(ticket.id, "I'll check the recording failure.", person=_SUPPORT)
        again = Inbox.open(
            SAMPLES, analyzer=Hanging(), store=PostgresTicketStore(self.dsn), clock=clock, wait_limit=0.05,
        )
        signed = again.get(ticket.id, _SUPPORT)
        self.assertIsNotNone(signed)
        assert signed is not None
        self.assertEqual(
            [(reply.author, reply.body) for reply in signed.replies],
            [(_SUPPORT.name, "I'll check the recording failure.")],
        )
        self.assertIsNone(signed.pending)
        seen = again.open_customer(ticket.id, ticket.credential)
        self.assertEqual(
            [(reply.author, reply.body) for reply in seen.replies],
            [(_SUPPORT.name, "I'll check the recording failure.")],
        )


class _Clock:
    def __init__(self) -> None:
        self.current = datetime(2026, 11, 18, 6, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)
