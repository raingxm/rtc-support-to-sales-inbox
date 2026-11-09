from api.inbox import Inbox, SAMPLES, _Draft
from api.main import create_app


class FixedAnalyzer:
    async def draft(self, body: str) -> _Draft:
        return _Draft(
            title="Recording failures and pilot",
            kind="mixed",
            summary="Check the recording failures and follow up on the pilot.",
            support_steps=["Ask when the recordings failed."],
            evidence=["launch a pilot next month"],
            questions=["What will the pilot cover?"],
        )


app = create_app(Inbox.open(SAMPLES, analyzer=FixedAnalyzer()))
