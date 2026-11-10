# RTC Support-to-Sales Inbox

A demo workbench for technical support teams at real-time communications (RTC) providers. A support agent can keep troubleshooting a ticket while handing a migration or pilot opportunity to a solutions engineer.

## Run the demo locally

Use Node.js 20.9 or newer and Python 3.12. Run these commands from the repository root in PowerShell.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r api/requirements.txt
npm.cmd ci
```

Start FastAPI in one terminal.

```powershell
.venv/Scripts/python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Start Next.js in a second terminal.

```powershell
npm.cmd run dev
```

Open [the workbench](http://127.0.0.1:3000). On macOS or Linux, use `.venv/bin/python` and `npm` in place of the PowerShell commands.

## Walk through the three tickets

1. Open **RTC-1042**. Check the original recording report and the evidence for a migration pilot. Select a solutions engineer and confirm the handoff. The support ticket remains open.
2. Open **RTC-1041**. Review the Flutter token troubleshooting steps.
3. Open **RTC-1040**. Review what to ask about the recording use case and launch date.

FastAPI serves three fictional tickets with prepared triage results. You can review them and confirm a handoff without a model key. The demo uses in-memory storage when `DATABASE_URL` is empty.

## Analyze a new letter

Set `OPENAI_API_KEY` in the terminal that runs FastAPI, then restart the API. Set `OPENAI_MODEL` to override the default model, `gpt-5.4-mini`.

To use Quanzil, set `OPENAI_BASE_URL=https://quanzil.com/v1` and use a Quanzil key and a model that supports Responses API structured output. The base URL defaults to `https://api.openai.com/v1`. If you keep these settings in `.env`, load the file into the backend terminal before starting FastAPI.

1. Open **New letter**. Enter the customer name and paste a fictional customer message.
2. Click **Analyze letter**. The workbench selects the new ticket and shows its triage under **Live analysis**.
3. For an opportunity, compare each quote with the highlighted text in the customer message.

The API sends the message body to the configured model provider for analysis. It adds the ticket only after every evidence quote matches the original text.

## Persist tickets and handoffs

Use a PostgreSQL database for the workbench. Set `DATABASE_URL` in the terminal that runs FastAPI. For example, a local development database named `rtc_inbox` with a dedicated user could use this configuration.

```dotenv
DATABASE_URL=postgresql://rtc_inbox:local_password@127.0.0.1:5432/rtc_inbox
```

Start FastAPI as above. It creates the two workbench tables and inserts the three samples if needed. The database user needs permission to create tables in the target schema. New tickets, original text, quote positions, and confirmed handoffs survive API restarts. Repeat confirmations return the owner who was first saved.

## Verify the workbench

With Chrome installed, run `npm run verify` from the repository root. Playwright starts a fresh API and workbench on ports 8100 and 3100. It tests the three samples, handoff, and new-letter analysis with a fixed model response. Run `npm run build` to check the production build.

To run the PostgreSQL integration tests, set `RTC_TEST_DATABASE_URL` to a development database whose user can create schemas. The tests create and remove an isolated schema. Run `python -m unittest discover -s tests -p "test_*.py"` with the project virtual environment active.
