import asyncio
import os
from threading import Barrier
from unittest import IsolatedAsyncioTestCase, skipUnless
from uuid import uuid4

from psycopg import connect, sql
from psycopg.conninfo import make_conninfo

from api.inbox import HandoffRejected, Inbox, Letter, Owner, QuoteRejected, SAMPLES, TicketNotFound, _Draft
from api.postgres import PostgresTicketStore


_TEST_DATABASE_URL = os.getenv("RTC_TEST_DATABASE_URL")
_PILOT = "We want to launch a pilot next month."


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
        assigned = inbox.confirm_handoff(ticket.id, "Maya Chen")
        sample_assigned = inbox.confirm_handoff("RTC-1042", "Jordan Lee")

        reopened = self.open_inbox()
        self.assertEqual([item.id for item in reopened.list_tickets()], [
            "RTC-1042", "RTC-1041", "RTC-1040", "RTC-1043",
        ])
        self.assertEqual(reopened.get(ticket.id), assigned)
        self.assertEqual(reopened.get("RTC-1042"), sample_assigned)
        self.assertEqual(reopened.confirm_handoff(ticket.id, "Jordan Lee").handoff.owner, "Maya Chen")

        with self.assertRaises(HandoffRejected):
            reopened.confirm_handoff("RTC-1041", "Maya Chen")
        with self.assertRaises(TicketNotFound):
            reopened.confirm_handoff("RTC-01043", "Maya Chen")
        with self.assertRaises(QuoteRejected):
            await reopened.submit(Letter(customer="Cypress Video", body="Recording failed."))
        self.assertEqual(len(reopened.list_tickets()), 4)

    async def test_concurrent_confirmations_store_one_owner(self) -> None:
        first_inbox = self.open_inbox()
        second_inbox = self.open_inbox()
        ticket = await first_inbox.submit(Letter(customer="Cypress Video", body=_PILOT))
        start = Barrier(2)

        def confirm(inbox: Inbox, owner: Owner):
            start.wait(timeout=5)
            return inbox.confirm_handoff(ticket.id, owner).handoff

        first, second = await asyncio.gather(
            asyncio.to_thread(confirm, first_inbox, "Maya Chen"),
            asyncio.to_thread(confirm, second_inbox, "Jordan Lee"),
        )
        self.assertIsNotNone(first)
        self.assertEqual(first, second)
        with connect(self.dsn) as connection:
            rows = connection.execute("SELECT ticket_number, owner FROM rtc_handoffs").fetchall()
        self.assertEqual(rows, [(1043, first.owner)])
