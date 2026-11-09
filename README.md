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

FastAPI serves three fictional tickets with prepared triage results. Handoffs are shared by browsers using the same API process and reset when that process stops. No model key or database is needed.

## Verify the workbench

With Chrome installed, run `npm run verify` from the repository root. Playwright starts a fresh API and workbench on ports 8100 and 3100. It exercises the three tickets against the real API. Run `npm run build` to check the production build.

The next milestone adds model analysis for new tickets. A later milestone stores tickets and confirmed handoffs in PostgreSQL.
