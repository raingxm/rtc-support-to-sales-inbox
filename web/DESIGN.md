---
version: alpha
colors:
  ink: "#17273b"
  canvas: "#f1f3f7"
  paper: "#ffffff"
  navy: "#14243a"
  primary: "#244cbb"
  support: "#526078"
  opportunity: "#155c51"
  clarification: "#75490c"
typography:
  body:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "15px"
    lineHeight: 1.55
  mono:
    fontFamily: "Cascadia Mono, Consolas, monospace"
    fontSize: "11px"
rounded:
  panel: "12px"
  card: "8px"
  control: "6px"
spacing:
  workspaceGap: "18px"
  panelInset: "22px"
components:
  workspace:
    backgroundColor: "{colors.canvas}"
  topbar:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.paper}"
  supportLabel:
    textColor: "{colors.support}"
  opportunityLabel:
    textColor: "{colors.opportunity}"
  clarificationLabel:
    textColor: "{colors.clarification}"
  confirmButton:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.paper}"
    rounded: "{rounded.control}"
  ticket:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
---

# Relay Desk design

## Overview

This is an English ticket desk for RTC support agents. The source message anchors each ticket. Separate tracks show who continues troubleshooting and who should follow up.

## Colors

Navy marks the workspace frame. Blue indicates selection and actions. Slate, teal, and amber distinguish support, opportunity, and clarification. Text and icons name each track independently of color. Runtime tokens live in the root of app/globals.css.

## Typography

Use the system sans stack for content and native controls. Use monospaced labels for ticket identifiers and panel captions.

## Layout

Show the queue beside ticket details on desktop. Move the queue above the details below 680px. Keep the source message visible above its triage result.

## Elevation & Depth

Use borders to separate work areas. Reserve the inset rail for the selected ticket.

## Shapes

Keep the panel, track, and control radii distinct so the visual hierarchy survives narrow screens.

## Components

The ticket queue uses native buttons with a pressed state. The handoff form uses a labeled native select and a confirm button. Pending and error messages stay beside the action. Successful assignments replace the form with a receipt and preserve the ticket detail.

## Do's and Don'ts

- Use the customer's wording for opportunity evidence.
- Keep the support status visible after a handoff.
- Show clarification questions for incomplete requests.
- Avoid decorative charts and controls with no action.
