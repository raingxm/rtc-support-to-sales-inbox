import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from pydantic import ValidationError

from api.inbox import (
    AnalysisFailed, DocumentationPage, Inbox, Letter, NotAuthenticated, QuoteRejected, SAMPLES,
    SupportPerson, Ticket, TicketNotFound, _Draft, quote_text,
)
from api.main import _configured_inbox, load_local_env
from api.model_analyzer import configured_analyzer


SUPPORT = SupportPerson(name="Riley Cho")


class SampleEvidenceTest(TestCase):
    def test_sample_evidence_keeps_its_original_positions_and_wording(self):
        inbox = Inbox.open(SAMPLES)
        ticket, *_ = inbox.list_tickets(SUPPORT)

        self.assertEqual(ticket.id, "RTC-1042")
        self.assertEqual(ticket.origin, "sample")
        self.assertEqual(ticket.triage.kind, "mixed")
        self.assertEqual(
            [(span.start, span.end) for span in ticket.triage.evidence],
            [(53, 88), (101, 126)],
        )
        self.assertEqual(
            [quote_text(ticket.messages[span.message].body, span) for span in ticket.triage.evidence],
            ["evaluating a move from Twilio Video", "launch a pilot next month"],
        )


class NewLetterTest(IsolatedAsyncioTestCase):
    async def test_one_unmatched_quote_rejects_the_whole_letter(self):
        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                return _Draft(
                    title="Recording issues and migration pilot",
                    kind="mixed",
                    summary="Follow up on recording and the pilot.",
                    support_steps=[],
                    evidence=[
                        "launch a pilot next month",
                        "We are evaluating a migration away from Twilio and want a pilot.",
                    ],
                    questions=[],
                )

        inbox = Inbox.open(SAMPLES, analyzer=Analyzer())
        samples = inbox.list_tickets(SUPPORT)
        original = samples[0]

        with self.assertRaises(QuoteRejected) as failure:
            await inbox.submit(Letter(customer=original.customer, body=original.messages[0].body))

        self.assertEqual(failure.exception.reason, "not-in-letter")
        self.assertEqual(inbox.list_tickets(SUPPORT), samples)


class AppendedMessageTest(IsolatedAsyncioTestCase):
    async def test_a_later_customer_message_stays_on_the_ticket_and_can_change_unconfirmed_triage(self):
        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                if "launch a pilot next month" in body:
                    return _Draft(
                        title="Pilot follow-up",
                        kind="mixed",
                        summary="Route the pilot.",
                        support_steps=["Ask for the failure time."],
                        evidence=["launch a pilot next month"],
                        questions=["How many calls?"],
                    )
                return _Draft(
                    title="Join help",
                    kind="support",
                    summary="Troubleshoot the join error.",
                    support_steps=["Check the token expiry."],
                    evidence=[],
                    questions=[],
                )

        inbox = Inbox.open(SAMPLES, analyzer=Analyzer())
        opened = await inbox.submit(Letter(
            customer="Northwind Studio",
            body="My join call returns an invalid token error.",
        ))

        updated = await inbox.append_customer_message(
            opened.id,
            "We want to launch a pilot next month.",
            credential=opened.credential,
        )

        self.assertEqual(updated.id, opened.id)
        self.assertEqual(updated.customer, "Northwind Studio")
        self.assertEqual([message.body for message in updated.messages], [
            "My join call returns an invalid token error.",
            "We want to launch a pilot next month.",
        ])
        self.assertEqual(updated.triage.kind, "mixed")
        self.assertEqual(updated.triage.summary, "Route the pilot.")
        evidence = updated.triage.evidence[0]
        self.assertEqual(
            quote_text(updated.messages[evidence.message].body, evidence),
            "launch a pilot next month",
        )
        self.assertEqual(inbox.get(opened.id, SUPPORT), updated)
        self.assertEqual(len(inbox.list_tickets(SUPPORT)), 4)

    async def test_a_quote_missing_from_the_customer_messages_leaves_the_ticket_unchanged(self):
        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                if "follow-up" in body:
                    return _Draft(
                        title="Missing quote",
                        kind="mixed",
                        summary="This quote is not in the conversation.",
                        support_steps=[],
                        evidence=["a sentence the customer did not write"],
                        questions=[],
                    )
                return _Draft(
                    title="Join help",
                    kind="support",
                    summary="Troubleshoot the join error.",
                    support_steps=["Check the token expiry."],
                    evidence=[],
                    questions=[],
                )

        inbox = Inbox.open(SAMPLES, analyzer=Analyzer())
        opened = await inbox.submit(Letter(
            customer="Northwind Studio",
            body="My join call returns an invalid token error.",
        ))

        with self.assertRaises(QuoteRejected) as failure:
            await inbox.append_customer_message(
                opened.id, "This follow-up still has no pilot.", credential=opened.credential,
            )

        self.assertEqual(failure.exception.reason, "not-in-letter")
        self.assertEqual(inbox.get(opened.id, SUPPORT), opened)

    async def test_a_later_message_keeps_a_confirmed_handoff_and_its_triage(self):
        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                if "invalid token" in body:
                    return _Draft(
                        title="Join help",
                        kind="support",
                        summary="Troubleshoot the token.",
                        support_steps=["Check the token expiry."],
                        evidence=[],
                        questions=[],
                    )
                return _Draft(
                    title="Pilot",
                    kind="mixed",
                    summary="Route the pilot.",
                    support_steps=[],
                    evidence=["launch a pilot next month"],
                    questions=[],
                )

        inbox = Inbox.open(SAMPLES, analyzer=Analyzer())
        opened = await inbox.submit(Letter(
            customer="Harborline Labs",
            body="We want to launch a pilot next month.",
        ))
        assigned = inbox.confirm_handoff(opened.id, "Maya Chen", person=SUPPORT)

        updated = await inbox.append_customer_message(
            opened.id,
            "My join call returns an invalid token error.",
            credential=opened.credential,
        )

        self.assertEqual([message.body for message in updated.messages], [
            "We want to launch a pilot next month.",
            "My join call returns an invalid token error.",
        ])
        self.assertEqual(updated.handoff, assigned.handoff)
        self.assertEqual(updated.triage, assigned.triage)

    async def test_a_handoff_confirmed_during_analysis_stays_on_the_ticket(self):
        started = asyncio.Event()
        release = asyncio.Event()

        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                if "\n\n" in body:
                    started.set()
                    await release.wait()
                    return _Draft(
                        title="Join help",
                        kind="support",
                        summary="Troubleshoot the token.",
                        support_steps=["Check the token expiry."],
                        evidence=[],
                        questions=[],
                    )
                return _Draft(
                    title="Pilot",
                    kind="mixed",
                    summary="Route the pilot.",
                    support_steps=[],
                    evidence=["launch a pilot next month"],
                    questions=[],
                )

        inbox = Inbox.open(SAMPLES, analyzer=Analyzer())
        opened = await inbox.submit(Letter(
            customer="Harborline Labs",
            body="We want to launch a pilot next month.",
        ))
        follow_up = asyncio.create_task(inbox.append_customer_message(
            opened.id,
            "My join call returns an invalid token error.",
            credential=opened.credential,
        ))
        await started.wait()
        assigned = await asyncio.to_thread(inbox.confirm_handoff, opened.id, "Maya Chen", person=SUPPORT)
        release.set()
        updated = await follow_up

        self.assertEqual([message.body for message in updated.messages], [
            "We want to launch a pilot next month.",
            "My join call returns an invalid token error.",
        ])
        self.assertEqual(updated.handoff, assigned.handoff)
        self.assertEqual(updated.triage, assigned.triage)

    async def test_a_later_message_can_quote_an_earlier_customer_message(self):
        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                return _Draft(
                    title="Pilot",
                    kind="mixed",
                    summary="Updated reading." if "\n\n" in body else "First reading.",
                    support_steps=[],
                    evidence=["launch a pilot next month"],
                    questions=[],
                )

        inbox = Inbox.open(SAMPLES, analyzer=Analyzer())
        opened = await inbox.submit(Letter(
            customer="Harborline Labs",
            body="We want to launch a pilot next month.",
        ))

        updated = await inbox.append_customer_message(
            opened.id, "The recordings are still failing.", credential=opened.credential,
        )

        self.assertEqual(updated.triage.summary, "Updated reading.")
        evidence = updated.triage.evidence[0]
        self.assertEqual(evidence.message, 0)
        self.assertEqual(
            quote_text(updated.messages[evidence.message].body, evidence),
            "launch a pilot next month",
        )

    async def test_a_blank_follow_up_is_refused_and_an_unknown_ticket_is_missing(self):
        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                return _Draft(
                    title="Join help",
                    kind="support",
                    summary="Troubleshoot the join error.",
                    support_steps=["Check the token expiry."],
                    evidence=[],
                    questions=[],
                )

        inbox = Inbox.open(SAMPLES, analyzer=Analyzer())
        opened = await inbox.submit(Letter(
            customer="Northwind Studio",
            body="My join call returns an invalid token error.",
        ))

        with self.assertRaises(ValidationError):
            await inbox.append_customer_message(opened.id, "   ", credential=opened.credential)
        self.assertEqual(inbox.get(opened.id, SUPPORT), opened)

        with self.assertRaises(TicketNotFound):
            await inbox.append_customer_message("RTC-9999", "Still here.", credential="not-an-address")


class CustomerWordsFirstTest(IsolatedAsyncioTestCase):
    async def test_the_ticket_and_its_address_exist_before_analysis_returns(self):
        started = asyncio.Event()
        release = asyncio.Event()

        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                started.set()
                await release.wait()
                return _Draft(
                    title="Join help",
                    kind="support",
                    summary="Troubleshoot the join error.",
                    support_steps=["Check the token expiry."],
                    evidence=[],
                    questions=[],
                )

        inbox = Inbox.open(SAMPLES, analyzer=Analyzer())
        body = "My join call returns an invalid token error."
        submitting = asyncio.create_task(inbox.submit(Letter(customer="Northwind Studio", body=body)))
        try:
            await asyncio.wait_for(started.wait(), timeout=2)
            stored = next(
                ticket for ticket in inbox.list_tickets(SUPPORT)
                if ticket.origin == "live" and ticket.customer == "Northwind Studio"
            )
            self.assertEqual([message.body for message in stored.messages], [body])
            self.assertTrue(stored.credential)
            self.assertNotEqual(stored.credential, stored.id)

            opened = inbox.open_customer(stored.id, stored.credential)
            self.assertEqual(opened.id, stored.id)
            self.assertEqual([message.body for message in opened.messages], [body])
            self.assertEqual(list(opened.replies), [])
            self.assertNotIn("pending", opened.model_dump())
            self.assertNotIn("triage", opened.model_dump())

            with self.assertRaises(TicketNotFound):
                inbox.open_customer(stored.id, "")
            with self.assertRaises(TicketNotFound):
                inbox.open_customer(stored.id, stored.id)
            other = next(ticket for ticket in inbox.list_tickets(SUPPORT) if ticket.id != stored.id)
            with self.assertRaises(TicketNotFound):
                inbox.open_customer(stored.id, other.credential)
            with self.assertRaises(TicketNotFound):
                inbox.open_customer(other.id, stored.credential)
        finally:
            release.set()
            await submitting

    async def test_a_follow_up_is_on_the_ticket_before_its_analysis_returns(self):
        started = asyncio.Event()
        release = asyncio.Event()

        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                if "\n\n" in body:
                    started.set()
                    await release.wait()
                return _Draft(
                    title="Join help",
                    kind="support",
                    summary="Troubleshoot the join error.",
                    support_steps=["Check the token expiry."],
                    evidence=[],
                    questions=[],
                )

        inbox = Inbox.open(SAMPLES, analyzer=Analyzer())
        first = "My join call returns an invalid token error."
        follow_up = "The recordings are still failing."
        opened = await inbox.submit(Letter(customer="Northwind Studio", body=first))
        appending = asyncio.create_task(inbox.append_customer_message(
            opened.id, follow_up, credential=opened.credential,
        ))
        try:
            await asyncio.wait_for(started.wait(), timeout=2)
            stored = inbox.get(opened.id, SUPPORT)
            self.assertIsNotNone(stored)
            assert stored is not None
            self.assertEqual([message.body for message in stored.messages], [first, follow_up])
            customer = inbox.open_customer(opened.id, opened.credential)
            self.assertEqual([message.body for message in customer.messages], [first, follow_up])
            self.assertEqual(customer.replies, ())
        finally:
            release.set()
            updated = await appending

        self.assertEqual([message.body for message in updated.messages], [first, follow_up])
        self.assertEqual(updated.triage.summary, "Troubleshoot the join error.")

    async def test_a_timed_out_analysis_keeps_the_words_and_shows_support_how_long_the_customer_has_waited(self):
        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                await asyncio.Event().wait()
                raise AssertionError("unreachable")

        clock = _Clock()
        inbox = Inbox.open(SAMPLES, analyzer=Analyzer(), clock=clock, wait_limit=0.05)
        body = "My join call returns an invalid token error."
        ticket = await inbox.submit(Letter(customer="Northwind Studio", body=body))
        clock.advance(90)

        customer = inbox.open_customer(ticket.id, ticket.credential)
        self.assertEqual(customer.id, ticket.id)
        self.assertEqual([message.body for message in customer.messages], [body])
        self.assertEqual(customer.replies, ())
        self.assertNotIn("pending", customer.model_dump())
        self.assertNotIn("triage", customer.model_dump())

        support = inbox.get(ticket.id, SUPPORT)
        self.assertIsNotNone(support)
        assert support is not None
        self.assertEqual(support.id, ticket.id)
        self.assertEqual([message.body for message in support.messages], [body])
        self.assertEqual(support.replies, ())
        self.assertIsNotNone(support.pending)
        assert support.pending is not None
        self.assertEqual(support.pending.reason, "已经停止等待")
        self.assertEqual(support.pending.waiting_seconds, 90)

    async def test_waiting_is_measured_from_the_latest_customer_message(self):
        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                if "\n\n" in body:
                    await asyncio.Event().wait()
                return _Draft(
                    title="Join help",
                    kind="support",
                    summary="Troubleshoot the join error.",
                    support_steps=["Check the token expiry."],
                    evidence=[],
                    questions=[],
                )

        clock = _Clock()
        inbox = Inbox.open(SAMPLES, analyzer=Analyzer(), clock=clock, wait_limit=0.05)
        first = "My join call returns an invalid token error."
        follow_up = "The recordings are still failing."
        opened = await inbox.submit(Letter(customer="Northwind Studio", body=first))
        clock.advance(600)
        await inbox.append_customer_message(opened.id, follow_up, credential=opened.credential)
        clock.advance(90)

        support = inbox.get(opened.id, SUPPORT)
        self.assertIsNotNone(support)
        assert support is not None and support.pending is not None
        self.assertEqual([message.body for message in support.messages], [first, follow_up])
        self.assertEqual(support.pending.reason, "已经停止等待")
        self.assertEqual(support.pending.waiting_seconds, 90)
        customer = inbox.open_customer(opened.id, opened.credential)
        self.assertEqual([message.body for message in customer.messages], [first, follow_up])
        self.assertEqual(customer.replies, ())
        self.assertNotIn("pending", customer.model_dump())

    async def test_a_failed_analysis_keeps_the_words_without_a_reply(self):
        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                raise AnalysisFailed

        clock = _Clock()
        inbox = Inbox.open(SAMPLES, analyzer=Analyzer(), clock=clock)
        body = "My join call returns an invalid token error."
        ticket = await inbox.submit(Letter(customer="Northwind Studio", body=body))
        clock.advance(30)

        customer = inbox.open_customer(ticket.id, ticket.credential)
        self.assertEqual([message.body for message in customer.messages], [body])
        self.assertEqual(customer.replies, ())
        self.assertNotIn("pending", customer.model_dump())
        support = inbox.get(ticket.id, SUPPORT)
        self.assertIsNotNone(support)
        assert support is not None and support.pending is not None
        self.assertEqual(support.id, "RTC-1043")
        self.assertEqual(support.pending.reason, "已经停止等待")
        self.assertEqual(support.pending.waiting_seconds, 30)

    async def test_a_support_reply_is_signed_on_the_customer_and_support_entrances(self):
        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                raise AnalysisFailed

        inbox = Inbox.open(SAMPLES, analyzer=Analyzer())
        body = "My join call returns an invalid token error."
        ticket = await inbox.submit(Letter(customer="Northwind Studio", body=body))
        person = SupportPerson(name="Riley Cho")

        with self.assertRaises(ValidationError):
            inbox.reply(ticket.id, "   ", person=person)
        self.assertEqual(inbox.open_customer(ticket.id, ticket.credential).replies, ())

        inbox.reply(ticket.id, "I'll check the token expiry with you.", person=person)

        customer = inbox.open_customer(ticket.id, ticket.credential)
        self.assertEqual([message.body for message in customer.messages], [body])
        self.assertEqual(
            [(reply.author, reply.body) for reply in customer.replies],
            [("Riley Cho", "I'll check the token expiry with you.")],
        )
        self.assertNotIn("pending", customer.model_dump())

        support = inbox.get(ticket.id, SUPPORT)
        self.assertIsNotNone(support)
        assert support is not None
        self.assertEqual(
            [(reply.author, reply.body) for reply in support.replies],
            [("Riley Cho", "I'll check the token expiry with you.")],
        )
        self.assertIsNone(support.pending)

    async def test_a_reply_sent_while_analysis_is_still_running_is_not_put_back_into_pending(self):
        started = asyncio.Event()
        release = asyncio.Event()

        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                started.set()
                await release.wait()
                raise TimeoutError

        inbox = Inbox.open(SAMPLES, analyzer=Analyzer())
        body = "My join call returns an invalid token error."
        submitting = asyncio.create_task(inbox.submit(Letter(customer="Northwind Studio", body=body)))
        await asyncio.wait_for(started.wait(), timeout=2)
        stored = next(
            ticket for ticket in inbox.list_tickets(SUPPORT)
            if ticket.origin == "live" and ticket.customer == "Northwind Studio"
        )
        inbox.reply(stored.id, "I'll check the token expiry with you.", person=SUPPORT)
        release.set()
        ticket = await submitting

        self.assertIsNone(ticket.pending)
        self.assertEqual(
            [(reply.author, reply.body) for reply in ticket.replies],
            [("Riley Cho", "I'll check the token expiry with you.")],
        )
        customer = inbox.open_customer(stored.id, stored.credential)
        self.assertEqual(
            [(reply.author, reply.body) for reply in customer.replies],
            [("Riley Cho", "I'll check the token expiry with you.")],
        )
        self.assertNotIn("pending", customer.model_dump())
        support = inbox.get(stored.id, SUPPORT)
        assert support is not None
        self.assertIsNone(support.pending)

    async def test_a_later_message_after_a_reply_can_stop_waiting_again(self):
        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                if "\n\n" in body:
                    raise TimeoutError
                raise AnalysisFailed

        inbox = Inbox.open(SAMPLES, analyzer=Analyzer())
        first = "My join call returns an invalid token error."
        follow_up = "The recordings are still failing."
        opened = await inbox.submit(Letter(customer="Northwind Studio", body=first))
        inbox.reply(opened.id, "I'll check the token expiry with you.", person=SUPPORT)
        updated = await inbox.append_customer_message(opened.id, follow_up, credential=opened.credential)

        self.assertIsNotNone(updated.pending)
        assert updated.pending is not None
        self.assertEqual(updated.pending.reason, "已经停止等待")
        self.assertEqual(
            [(reply.author, reply.body) for reply in updated.replies],
            [("Riley Cho", "I'll check the token expiry with you.")],
        )
        self.assertEqual([message.body for message in updated.messages], [first, follow_up])

    async def test_a_customer_cannot_add_to_a_ticket_without_its_address(self):
        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                return _Draft(
                    title="Join help",
                    kind="support",
                    summary="Troubleshoot the join error.",
                    support_steps=["Check the token expiry."],
                    evidence=[],
                    questions=[],
                )

        inbox = Inbox.open(SAMPLES, analyzer=Analyzer())
        opened = await inbox.submit(Letter(
            customer="Northwind Studio",
            body="My join call returns an invalid token error.",
        ))
        other = inbox.list_tickets(SUPPORT)[0]

        with self.assertRaises(TicketNotFound):
            await inbox.append_customer_message(opened.id, "Still failing.", credential=other.credential)
        support = inbox.get(opened.id, SUPPORT)
        self.assertIsNotNone(support)
        assert support is not None
        self.assertEqual([message.body for message in support.messages], [
            "My join call returns an invalid token error.",
        ])

        updated = await inbox.append_customer_message(
            opened.id, "Still failing.", credential=opened.credential,
        )
        self.assertEqual([message.body for message in updated.messages], [
            "My join call returns an invalid token error.",
            "Still failing.",
        ])


class SupportSignInTest(TestCase):
    def test_an_anonymous_request_cannot_list_tickets_or_confirm_a_handoff(self):
        inbox = Inbox.open(SAMPLES)

        with self.assertRaises(NotAuthenticated):
            inbox.list_tickets()
        with self.assertRaises(NotAuthenticated):
            inbox.get("RTC-1042")
        with self.assertRaises(NotAuthenticated):
            inbox.confirm_handoff("RTC-1042", "Maya Chen")

        listed = inbox.list_tickets(SUPPORT)
        self.assertEqual(listed[0].id, "RTC-1042")
        assigned = inbox.confirm_handoff("RTC-1042", "Maya Chen", person=SUPPORT)
        self.assertEqual(assigned.handoff.owner, "Maya Chen")


class LateQuotedReplyTest(IsolatedAsyncioTestCase):
    async def test_a_late_quoted_result_is_an_unsigned_reply_on_both_entrances_and_leaves_pending(self):
        release = asyncio.Event()
        quote = "Cloud recording can be stored in COS or VOD."
        page = "https://trtc.io/document/45169"

        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                await release.wait()
                return _Draft(
                    title="Cloud recording",
                    kind="support",
                    summary="The opened page says where cloud recording can be stored.",
                    support_steps=["Open the cloud recording page."],
                    evidence=[],
                    questions=[],
                )

        class Documents:
            async def open(self, body: str) -> DocumentationPage:
                await release.wait()
                return DocumentationPage(url=page, quote=quote)

        inbox = Inbox.open(
            SAMPLES, analyzer=Analyzer(), documents=Documents(), wait_limit=0.05,
        )
        body = "Do you support cloud recording?"
        ticket = await inbox.submit(Letter(customer="Cedarline Media", body=body))

        self.assertEqual([message.body for message in ticket.messages], [body])
        self.assertEqual(ticket.replies, ())
        self.assertIsNotNone(ticket.pending)
        assert ticket.pending is not None
        self.assertEqual(ticket.pending.reason, "已经停止等待")
        self.assertIsNone(ticket.triage)

        release.set()
        await self._wait_until(lambda: len(self._support(inbox, ticket.id).replies) == 1)

        expected = (None, "Cloud recording can be stored in COS or VOD.\nhttps://trtc.io/document/45169")
        support = inbox.get(ticket.id, SUPPORT)
        assert support is not None
        self.assertIsNone(support.pending)
        self.assertEqual(support.triage.summary, "The opened page says where cloud recording can be stored.")
        self.assertEqual([(reply.author, reply.body) for reply in support.replies], [expected])
        customer = inbox.open_customer(ticket.id, ticket.credential)
        self.assertEqual([(reply.author, reply.body) for reply in customer.replies], [expected])
        self.assertNotIn("pending", customer.model_dump())
        self.assertNotIn("Riley Cho", customer.model_dump_json())

    async def test_an_unopened_page_replies_that_it_cannot_answer_and_keeps_the_wait(self):
        started = asyncio.Event()
        release = asyncio.Event()

        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                return _Draft(
                    title="Cloud recording",
                    kind="clarify",
                    summary="The documentation page did not open.",
                    support_steps=[],
                    evidence=[],
                    questions=["When do you want to start the pilot?"],
                )

        class Documents:
            async def open(self, body: str) -> None:
                started.set()
                await release.wait()
                return None

        clock = _Clock()
        inbox = Inbox.open(
            SAMPLES, analyzer=Analyzer(), documents=Documents(), clock=clock, wait_limit=1,
        )
        body = "Do you support cloud recording?"
        submitting = asyncio.create_task(inbox.submit(Letter(customer="Cedarline Media", body=body)))
        await asyncio.wait_for(started.wait(), timeout=2)
        clock.advance(30)
        release.set()
        ticket = await submitting

        self.assertEqual(
            [(reply.author, reply.body) for reply in ticket.replies],
            [(None, "I can't answer this.")],
        )
        self.assertNotIn("pilot", ticket.replies[0].body.lower())
        self.assertNotIn("migration", ticket.replies[0].body.lower())
        self.assertIsNotNone(ticket.pending)
        assert ticket.pending is not None
        self.assertEqual(ticket.pending.reason, "没有打开的公开文档")
        self.assertEqual(ticket.pending.waiting_seconds, 30)

        clock.advance(60)
        support = self._support(inbox, ticket.id)
        assert support.pending is not None
        self.assertEqual(support.pending.reason, "没有打开的公开文档")
        self.assertEqual(support.pending.waiting_seconds, 90)
        customer = inbox.open_customer(ticket.id, ticket.credential)
        self.assertEqual(
            [(reply.author, reply.body) for reply in customer.replies],
            [(None, "I can't answer this.")],
        )
        self.assertNotIn("pending", customer.model_dump())

        inbox.reply(ticket.id, "I'll look up the recording page.", person=SUPPORT)
        self.assertIsNone(self._support(inbox, ticket.id).pending)

        chinese = await inbox.submit(Letter(customer="北风", body="云端录制可以存到对象存储吗？"))
        self.assertEqual(
            [(reply.author, reply.body) for reply in chinese.replies],
            [(None, "这次答不了。")],
        )
        self.assertIsNotNone(chinese.pending)
        assert chinese.pending is not None
        self.assertEqual(chinese.pending.reason, "没有打开的公开文档")

    async def test_waiting_follows_the_latest_message_when_a_later_page_also_stays_unopened(self):
        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                return _Draft(
                    title="Cloud recording",
                    kind="clarify",
                    summary="The documentation page did not open.",
                    support_steps=[],
                    evidence=[],
                    questions=[],
                )

        class Documents:
            async def open(self, body: str) -> None:
                return None

        clock = _Clock()
        inbox = Inbox.open(
            SAMPLES, analyzer=Analyzer(), documents=Documents(), clock=clock, wait_limit=1,
        )
        opened = await inbox.submit(Letter(
            customer="Cedarline Media", body="Do you support cloud recording?",
        ))
        clock.advance(600)
        updated = await inbox.append_customer_message(
            opened.id, "Can those recordings be stored on AWS?", credential=opened.credential,
        )
        clock.advance(40)

        support = self._support(inbox, opened.id)
        assert support.pending is not None
        self.assertEqual([message.body for message in support.messages], [
            "Do you support cloud recording?",
            "Can those recordings be stored on AWS?",
        ])
        self.assertEqual(
            [reply.body for reply in support.replies],
            ["I can't answer this.", "I can't answer this."],
        )
        self.assertEqual(support.pending.reason, "没有打开的公开文档")
        self.assertEqual(support.pending.waiting_seconds, 40)
        self.assertEqual(updated.pending.waiting_seconds, 0)
        customer = inbox.open_customer(opened.id, opened.credential)
        self.assertEqual([reply.author for reply in customer.replies], [None, None])
        self.assertNotIn("pending", customer.model_dump())

    async def test_a_late_result_without_a_quote_stays_out_and_keeps_the_wait(self):
        release = asyncio.Event()

        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                await release.wait()
                return _Draft(
                    title="No page",
                    kind="support",
                    summary="This late reading has no documentation sentence.",
                    support_steps=["Ask for the SDK version."],
                    evidence=[],
                    questions=[],
                )

        class Documents:
            async def open(self, body: str) -> None:
                await release.wait()
                return None

        clock = _Clock()
        inbox = Inbox.open(
            SAMPLES, analyzer=Analyzer(), documents=Documents(), clock=clock, wait_limit=0.05,
        )
        ticket = await inbox.submit(Letter(
            customer="Cedarline Media", body="Do you support cloud recording?",
        ))
        clock.advance(25)
        release.set()
        await self._wait_until(
            lambda: (landed := self._support(inbox, ticket.id).triage) is not None
            and landed.summary == "This late reading has no documentation sentence.",
        )

        def still_waiting() -> None:
            support = self._support(inbox, ticket.id)
            assert support.pending is not None and support.triage is not None
            self.assertEqual(support.replies, ())
            self.assertEqual(support.triage.summary, "This late reading has no documentation sentence.")
            self.assertEqual(support.pending.reason, "已经停止等待")
            self.assertEqual(support.pending.waiting_seconds, 25)
            customer = inbox.open_customer(ticket.id, ticket.credential)
            self.assertEqual(customer.replies, ())

        await self._stays(still_waiting)

    async def test_a_late_result_without_a_quote_updates_the_reading_and_stays_unsent(self):
        release = asyncio.Event()
        first_quote = "Cloud recording can be stored in COS or VOD."

        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                if "\n\n" in body:
                    await release.wait()
                    return _Draft(
                        title="Unread follow-up",
                        kind="support",
                        summary="This late reading has no documentation sentence.",
                        support_steps=[],
                        evidence=[],
                        questions=[],
                    )
                return _Draft(
                    title="Cloud recording",
                    kind="support",
                    summary="First reading.",
                    support_steps=["Open the cloud recording page."],
                    evidence=[],
                    questions=[],
                )

        class Documents:
            async def open(self, body: str) -> DocumentationPage | None:
                if "\n\n" in body:
                    await release.wait()
                    return None
                return DocumentationPage(url="https://trtc.io/document/45169", quote=first_quote)

        inbox = Inbox.open(
            SAMPLES, analyzer=Analyzer(), documents=Documents(), wait_limit=0.05,
        )
        opened = await inbox.submit(Letter(
            customer="Cedarline Media", body="Do you support cloud recording?",
        ))
        followed = await inbox.append_customer_message(
            opened.id, "Can those recordings be stored on AWS?", credential=opened.credential,
        )
        self.assertEqual(followed.triage.summary, "First reading.")
        self.assertEqual(followed.pending.reason, "已经停止等待")
        release.set()
        await self._wait_until(
            lambda: self._support(inbox, opened.id).triage.summary
            == "This late reading has no documentation sentence.",
        )

        def reading_arrives_without_a_reply() -> None:
            support = self._support(inbox, opened.id)
            assert support.pending is not None and support.triage is not None
            self.assertEqual(support.triage.summary, "This late reading has no documentation sentence.")
            self.assertEqual(
                [(reply.author, reply.body) for reply in support.replies],
                [(None, "Cloud recording can be stored in COS or VOD.\nhttps://trtc.io/document/45169")],
            )
            self.assertEqual(support.pending.reason, "已经停止等待")

        await self._stays(reading_arrives_without_a_reply)

    async def test_a_late_result_for_an_earlier_conversation_is_dropped_with_its_reading(self):
        stale_release = asyncio.Event()
        latest_release = asyncio.Event()
        first_quote = "Cloud recording can be stored in COS or VOD."
        stale_quote = "Recordings can be stored on AWS."
        latest_quote = "A recording task can mix audio from several streams."

        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                gaps = body.count("\n\n")
                if gaps == 1:
                    await stale_release.wait()
                    return _Draft(
                        title="Stale reading",
                        kind="support",
                        summary="Stale reading.",
                        support_steps=[],
                        evidence=[],
                        questions=[],
                    )
                if gaps >= 2:
                    await latest_release.wait()
                    return _Draft(
                        title="Latest reading",
                        kind="support",
                        summary="Latest reading.",
                        support_steps=[],
                        evidence=[],
                        questions=[],
                    )
                return _Draft(
                    title="Cloud recording",
                    kind="support",
                    summary="First reading.",
                    support_steps=["Open the cloud recording page."],
                    evidence=[],
                    questions=[],
                )

        class Documents:
            async def open(self, body: str) -> DocumentationPage:
                gaps = body.count("\n\n")
                if gaps == 1:
                    await stale_release.wait()
                    return DocumentationPage(url="https://trtc.io/document/46960", quote=stale_quote)
                if gaps >= 2:
                    await latest_release.wait()
                    return DocumentationPage(url="https://trtc.io/document/45169", quote=latest_quote)
                return DocumentationPage(url="https://trtc.io/document/45169", quote=first_quote)

        inbox = Inbox.open(
            SAMPLES, analyzer=Analyzer(), documents=Documents(), wait_limit=0.05,
        )
        opened = await inbox.submit(Letter(
            customer="Cedarline Media", body="Do you support cloud recording?",
        ))
        self.assertEqual(self._support(inbox, opened.id).triage.summary, "First reading.")
        await inbox.append_customer_message(
            opened.id, "Can those recordings be stored on AWS?", credential=opened.credential,
        )
        await inbox.append_customer_message(
            opened.id, "Can one task mix several audio streams?", credential=opened.credential,
        )
        stale_release.set()

        def keeps_the_first_reading() -> None:
            support = self._support(inbox, opened.id)
            self.assertEqual(support.triage.summary, "First reading.")
            self.assertNotIn(stale_quote, [reply.body for reply in support.replies])
            customer = inbox.open_customer(opened.id, opened.credential)
            self.assertNotIn(stale_quote, [reply.body for reply in customer.replies])

        await self._stays(keeps_the_first_reading)

        latest_release.set()
        await self._wait_until(
            lambda: any(latest_quote in reply.body for reply in self._support(inbox, opened.id).replies),
        )
        support = self._support(inbox, opened.id)
        self.assertEqual(support.triage.summary, "Latest reading.")
        self.assertIsNone(support.pending)
        self.assertEqual(
            [reply.body for reply in support.replies],
            [
                "Cloud recording can be stored in COS or VOD.\nhttps://trtc.io/document/45169",
                "A recording task can mix audio from several streams.\nhttps://trtc.io/document/45169",
            ],
        )
        self.assertNotIn(stale_quote, [reply.body for reply in support.replies])
        self.assertEqual([reply.author for reply in support.replies], [None, None])

    async def test_a_late_quote_for_the_first_message_leaves_an_empty_reading_empty(self):
        first_release = asyncio.Event()
        second_release = asyncio.Event()
        stale_quote = "Cloud recording can be stored in COS or VOD."
        current_quote = "Recordings can be stored on AWS."

        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                if "\n\n" in body:
                    await second_release.wait()
                    return _Draft(
                        title="Current reading",
                        kind="support",
                        summary="Current reading.",
                        support_steps=[],
                        evidence=[],
                        questions=[],
                    )
                await first_release.wait()
                return _Draft(
                    title="Stale reading",
                    kind="support",
                    summary="Stale reading.",
                    support_steps=[],
                    evidence=[],
                    questions=[],
                )

        class Documents:
            async def open(self, body: str) -> DocumentationPage:
                if "\n\n" in body:
                    await second_release.wait()
                    return DocumentationPage(url="https://trtc.io/document/46960", quote=current_quote)
                await first_release.wait()
                return DocumentationPage(url="https://trtc.io/document/45169", quote=stale_quote)

        inbox = Inbox.open(
            SAMPLES, analyzer=Analyzer(), documents=Documents(), wait_limit=0.05,
        )
        opened = await inbox.submit(Letter(
            customer="Cedarline Media", body="Do you support cloud recording?",
        ))
        self.assertIsNone(opened.triage)
        await inbox.append_customer_message(
            opened.id, "Can those recordings be stored on AWS?", credential=opened.credential,
        )
        first_release.set()

        def stays_empty() -> None:
            support = self._support(inbox, opened.id)
            self.assertIsNone(support.triage)
            self.assertNotIn(stale_quote, [reply.body for reply in support.replies])
            self.assertEqual(support.replies, ())

        await self._stays(stays_empty)

        second_release.set()
        await self._wait_until(lambda: len(self._support(inbox, opened.id).replies) == 1)
        support = self._support(inbox, opened.id)
        self.assertEqual(support.triage.summary, "Current reading.")
        self.assertEqual(support.replies[0].body, "Recordings can be stored on AWS.\nhttps://trtc.io/document/46960")
        self.assertIsNone(support.replies[0].author)
        self.assertNotIn(stale_quote, support.replies[0].body)

    async def test_a_late_quote_after_a_support_reply_stays_out_of_the_conversation(self):
        release = asyncio.Event()
        quote = "Cloud recording can be stored in COS or VOD."

        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                await release.wait()
                return _Draft(
                    title="Cloud recording",
                    kind="support",
                    summary="Late reading.",
                    support_steps=["Open the cloud recording page."],
                    evidence=[],
                    questions=[],
                )

        class Documents:
            async def open(self, body: str) -> DocumentationPage:
                await release.wait()
                return DocumentationPage(url="https://trtc.io/document/45169", quote=quote)

        inbox = Inbox.open(
            SAMPLES, analyzer=Analyzer(), documents=Documents(), wait_limit=0.05,
        )
        ticket = await inbox.submit(Letter(
            customer="Cedarline Media", body="Do you support cloud recording?",
        ))
        inbox.reply(ticket.id, "I'll look up the recording page.", person=SUPPORT)
        release.set()
        await self._wait_until(
            lambda: (landed := self._support(inbox, ticket.id).triage) is not None
            and landed.summary == "Late reading.",
        )

        def only_the_signed_reply() -> None:
            support = self._support(inbox, ticket.id)
            assert support.triage is not None
            self.assertIsNone(support.pending)
            self.assertEqual(support.triage.summary, "Late reading.")
            expected = [("Riley Cho", "I'll look up the recording page.")]
            self.assertEqual([(reply.author, reply.body) for reply in support.replies], expected)
            customer = inbox.open_customer(ticket.id, ticket.credential)
            self.assertEqual([(reply.author, reply.body) for reply in customer.replies], expected)
            self.assertNotIn(quote, customer.model_dump_json())

        await self._stays(only_the_signed_reply)

    def _support(self, inbox: Inbox, ticket_id: str) -> Ticket:
        support = inbox.get(ticket_id, SUPPORT)
        self.assertIsNotNone(support)
        assert support is not None
        return support

    async def _wait_until(self, ready) -> None:
        deadline = asyncio.get_running_loop().time() + 2
        while asyncio.get_running_loop().time() < deadline:
            if ready():
                return
            await asyncio.sleep(0.01)
        self.fail("the ticket did not settle")

    async def _stays(self, check) -> None:
        deadline = asyncio.get_running_loop().time() + 0.5
        while asyncio.get_running_loop().time() < deadline:
            check()
            await asyncio.sleep(0.01)


class _Clock:
    def __init__(self) -> None:
        self.current = datetime(2026, 11, 18, 6, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)


class AnalysisTextTest(IsolatedAsyncioTestCase):
    async def test_credentials_stay_out_of_analysis_and_a_quoted_result_still_opens_the_ticket(self):
        seen: list[str] = []

        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                seen.append(body)
                return _Draft(
                    title="Join failed",
                    kind="mixed",
                    summary="Follow up on the join failure.",
                    support_steps=["Check the SDK version and the error time."],
                    evidence=["error code -100013"],
                    questions=[],
                )

        original = (
            "SDK 11.4 returned error code -100013 at 2026-11-18 14:02:07.\n"
            "UserSig: eJyrVgrxCdYrSy1SslIy0jNQ0gHzM1NS80oy0zPz0tJTi5KLAA\n"
            "SDKSecretKey: 89abcdef0123456789abcdef01234567"
        )
        inbox = Inbox.open(SAMPLES, analyzer=Analyzer())

        ticket = await inbox.submit(Letter(customer="Northwind Studio", body=original))

        self.assertEqual(seen, [
            "SDK 11.4 returned error code -100013 at 2026-11-18 14:02:07.\n",
        ])
        self.assertEqual(ticket.messages[0].body, original)
        self.assertEqual(
            quote_text(ticket.messages[0].body, ticket.triage.evidence[0]),
            "error code -100013",
        )

    async def test_a_later_message_keeps_its_credentials_out_of_analysis(self):
        seen: list[str] = []

        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                seen.append(body)
                if "\n\n" in body:
                    return _Draft(
                        title="Join failed",
                        kind="mixed",
                        summary="Follow up on the join failure.",
                        support_steps=["Check the error time."],
                        evidence=["error code -100013"],
                        questions=[],
                    )
                return _Draft(
                    title="Recording",
                    kind="support",
                    summary="Ask for the failure details.",
                    support_steps=["Ask for the error code."],
                    evidence=[],
                    questions=[],
                )

        inbox = Inbox.open(SAMPLES, analyzer=Analyzer())
        opened = await inbox.submit(Letter(
            customer="Northwind Studio",
            body="Recordings fail on SDK 11.4.",
        ))
        follow_up = (
            "It returned error code -100013 at 2026-11-18 14:02:07.\n"
            "UserSig: eJyrVgrxCdYrSy1SslIy0jNQ0gHzM1NS80oy0zPz0tJTi5KLAA\n"
            "SDKSecretKey: 89abcdef0123456789abcdef01234567"
        )

        updated = await inbox.append_customer_message(
            opened.id, follow_up, credential=opened.credential,
        )

        self.assertEqual(seen[1], (
            "Recordings fail on SDK 11.4.\n"
            "\n"
            "It returned error code -100013 at 2026-11-18 14:02:07.\n"
        ))
        self.assertEqual([message.body for message in updated.messages], [
            "Recordings fail on SDK 11.4.",
            follow_up,
        ])
        evidence = updated.triage.evidence[0]
        self.assertEqual(evidence.message, 1)
        self.assertEqual(
            quote_text(updated.messages[evidence.message].body, evidence),
            "error code -100013",
        )

    async def test_json_and_wrapped_credentials_stay_out_of_analysis(self):
        seen: list[str] = []
        user_sig = "eJyrVgrxCdYrSy1SslIy0jNQ0gHzM1NS80oy0zPz0tJTi5KLAA"
        secret_key = "89abcdef0123456789abcdef01234567"

        class Analyzer:
            async def draft(self, body: str) -> _Draft:
                seen.append(body)
                return _Draft(
                    title="Join failed",
                    kind="mixed",
                    summary="Follow up on the join failure.",
                    support_steps=["Check the SDK version and the error time."],
                    evidence=["error code -100013"],
                    questions=[],
                )

        original = (
            "SDK 11.4 returned error code -100013 at 2026-11-18 14:02:07.\n"
            f'{{"UserSig":"{user_sig}","SDKSecretKey":"{secret_key}"}}\n'
            "usersig=\n"
            f"{user_sig}\n"
            f"`sdkSecretKey`: {secret_key}"
        )
        inbox = Inbox.open(SAMPLES, analyzer=Analyzer())

        ticket = await inbox.submit(Letter(customer="Northwind Studio", body=original))

        analysis = seen[0]
        self.assertNotIn(user_sig, analysis)
        self.assertNotIn(secret_key, analysis)
        self.assertNotIn("usersig", analysis.lower())
        self.assertNotIn("sdksecretkey", analysis.lower())
        self.assertIn("SDK 11.4", analysis)
        self.assertIn("error code -100013", analysis)
        self.assertIn("2026-11-18 14:02:07", analysis)
        self.assertEqual(ticket.messages[0].body, original)
        self.assertEqual(
            quote_text(ticket.messages[0].body, ticket.triage.evidence[0]),
            "error code -100013",
        )


class StoredLetterTest(TestCase):
    def test_a_stored_letter_opens_as_one_customer_message(self):
        ticket = Ticket.model_validate({
            "id": "RTC-1042",
            "origin": "sample",
            "title": "Cloud recording availability",
            "customer": "Cedarline Media",
            "body": "Do you support cloud recording?",
            "triage": {
                "kind": "clarify",
                "summary": "Ask about the recording use case.",
                "support_steps": ["Confirm what the customer needs to record."],
                "questions": ["Do you have a planned launch date?"],
            },
        })

        self.assertEqual(
            [message.body for message in ticket.messages],
            ["Do you support cloud recording?"],
        )


class OpenAIResponseTest(IsolatedAsyncioTestCase):
    async def test_configured_analyzer_submits_original_body_and_reads_output_text(self):
        class Response(BytesIO):
            status = 200

        body = "  Recording failed. We want a pilot next month.\n"
        draft = {
            "title": "Recording issue and pilot",
            "kind": "mixed",
            "summary": "Follow up on the pilot and troubleshoot recording.",
            "support_steps": ["Ask for the call ID."],
            "evidence": ["We want a pilot next month."],
            "questions": [],
        }
        envelope = {
            "status": "completed",
            "output": [
                {"type": "reasoning", "summary": []},
                {"type": "message", "content": [{"type": "output_text", "text": json.dumps(draft)}]},
            ],
        }
        for base_url, host in (("", "api.openai.com"), ("https://quanzil.com/v1/", "quanzil.com")):
            with (
                self.subTest(base_url=base_url),
                patch.dict("os.environ", {
                    "OPENAI_API_KEY": "test-credential",
                    "OPENAI_MODEL": "test-model",
                    "OPENAI_BASE_URL": base_url,
                }, clear=True),
                patch("api.model_analyzer.HTTPSConnection") as connect,
            ):
                connection = connect.return_value
                connection.getresponse.return_value = Response(json.dumps(envelope).encode("utf-8"))
                inbox = Inbox.open(SAMPLES, analyzer=configured_analyzer())
                ticket = await inbox.submit(Letter(customer="Harborline Labs", body=body))

                self.assertEqual(connect.call_args.args, (host,))
                request = connection.request.call_args
                self.assertEqual(request.args, ("POST", "/v1/responses"))
                payload = json.loads(request.kwargs["body"])
                self.assertEqual(payload["model"], "test-model")
                self.assertEqual(payload["input"], body)
                self.assertIs(payload["store"], False)
                self.assertEqual(ticket.id, "RTC-1043")
                self.assertEqual(ticket.title, "Recording issue and pilot")
                self.assertEqual(ticket.messages[0].body, body)
                self.assertEqual(
                    quote_text(ticket.messages[0].body, ticket.triage.evidence[0]),
                    "We want a pilot next month.",
                )


class LocalEnvTest(TestCase):
    def test_a_dotenv_file_fills_unset_names_and_keeps_exported_values(self):
        with TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("OPENAI_API_KEY=from-file\nOPENAI_MODEL=from-file\n", encoding="utf-8")
            with patch.dict(os.environ, {"OPENAI_API_KEY": "from-shell"}, clear=True):
                load_local_env(env_file)
                self.assertEqual(os.environ["OPENAI_API_KEY"], "from-shell")
                self.assertEqual(os.environ["OPENAI_MODEL"], "from-file")

    def test_a_missing_dotenv_file_leaves_the_environment_unchanged(self):
        with TemporaryDirectory() as directory:
            with patch.dict(os.environ, {}, clear=True):
                load_local_env(Path(directory) / "missing.env")
                self.assertNotIn("OPENAI_API_KEY", os.environ)

    def test_startup_reads_the_dotenv_file_before_opening_the_inbox(self):
        with TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("OPENAI_MODEL=from-file\n", encoding="utf-8")
            with (
                patch("api.main._ENV_FILE", env_file),
                patch.dict(os.environ, {}, clear=True),
            ):
                inbox = _configured_inbox()
                self.assertEqual(os.environ["OPENAI_MODEL"], "from-file")
                self.assertEqual(len(inbox.list_tickets(SUPPORT)), 3)
