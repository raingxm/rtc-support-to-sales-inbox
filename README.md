# RTC Support-to-Sales Inbox

A planned portfolio project for technical support teams at real-time communications (RTC) providers. It identifies pilot, migration, and expansion signals in support tickets so a solutions engineer can follow up while support continues troubleshooting.

## Example workflow

A fictional customer reports intermittent call recording failures and mentions a migration pilot planned for next month. The inbox shows the original ticket, the quoted evidence for the pilot, and the open technical questions. A support agent reviews the suggestion and assigns a follow-up to a solutions engineer. The support ticket stays open.

## Development milestones

- [ ] Show three fictional tickets in an English workbench. Read them through FastAPI and walk through the handoff in the browser.
- [ ] Analyze a new ticket and check each evidence quote against the original text.
- [ ] Save the ticket and confirmed handoff in PostgreSQL. Repeated confirmation creates one task per ticket.
- [ ] Verify the workflow with new tickets and record a short demo.

The planned stack is Next.js with React and TypeScript, Python with FastAPI and Pydantic, and PostgreSQL.
