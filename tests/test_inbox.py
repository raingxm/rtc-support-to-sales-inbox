import json
from io import BytesIO
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from api.inbox import Inbox, Letter, QuoteRejected, SAMPLES, _Draft, quote_text
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
            [quote_text(ticket.body, span) for span in ticket.triage.evidence],
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
            await inbox.submit(Letter(customer=original.customer, body=original.body))

        self.assertEqual(failure.exception.reason, "not-in-letter")
        self.assertEqual(inbox.list_tickets(), samples)


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
                self.assertEqual(ticket.body, body)
                self.assertEqual(quote_text(ticket.body, ticket.triage.evidence[0]), "We want a pilot next month.")
