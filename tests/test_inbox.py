import asyncio
import json
import os
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from pydantic import ValidationError

from api.inbox import Inbox, Letter, QuoteRejected, SAMPLES, Ticket, TicketNotFound, _Draft, quote_text
from api.main import _configured_inbox, load_local_env
from api.model_analyzer import configured_analyzer


class SampleEvidenceTest(TestCase):
    def test_sample_evidence_keeps_its_original_positions_and_wording(self):
        inbox = Inbox.open(SAMPLES)
        ticket, *_ = inbox.list_tickets()

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
        samples = inbox.list_tickets()
        original = samples[0]

        with self.assertRaises(QuoteRejected) as failure:
            await inbox.submit(Letter(customer=original.customer, body=original.messages[0].body))

        self.assertEqual(failure.exception.reason, "not-in-letter")
        self.assertEqual(inbox.list_tickets(), samples)


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
        self.assertEqual(inbox.get(opened.id), updated)
        self.assertEqual(len(inbox.list_tickets()), 4)

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
            await inbox.append_customer_message(opened.id, "This follow-up still has no pilot.")

        self.assertEqual(failure.exception.reason, "not-in-letter")
        self.assertEqual(inbox.get(opened.id), opened)

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
        assigned = inbox.confirm_handoff(opened.id, "Maya Chen")

        updated = await inbox.append_customer_message(
            opened.id,
            "My join call returns an invalid token error.",
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
        ))
        await started.wait()
        assigned = await asyncio.to_thread(inbox.confirm_handoff, opened.id, "Maya Chen")
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

        updated = await inbox.append_customer_message(opened.id, "The recordings are still failing.")

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
            await inbox.append_customer_message(opened.id, "   ")
        self.assertEqual(inbox.get(opened.id), opened)

        with self.assertRaises(TicketNotFound):
            await inbox.append_customer_message("RTC-9999", "Still here.")


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

        updated = await inbox.append_customer_message(opened.id, follow_up)

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
                self.assertEqual(len(inbox.list_tickets()), 3)
