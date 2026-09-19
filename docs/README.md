# Azure Cost Visibility Platform — Documentation

A serverless Azure platform that gives a business owner real-time, plain-English visibility into their cloud spend, alerts them before a bill becomes a problem, and produces an automated weekly "what changed and why" report — with zero manual operation.

This project is built to do two jobs at once: solve a real and expensive problem for small businesses, and serve as a portfolio and marketing centrepiece demonstrating cloud architecture, automation, and data skills.

## Documents

| Doc | Audience | What it covers |
|-----|----------|----------------|
| [00 — Setup / deploy from scratch](00-setup.md) | Anyone deploying it | Ordered runbook to stand the platform up in a fresh environment |
| [01 — Executive summary](01-executive-summary.md) | Business owners, non-technical | The problem, the outcome, and the value, in plain language |
| [02 — Technical summary](02-technical-summary.md) | Engineers, reviewers | How the system works end to end |
| [03 — Tech stack](03-tech-stack.md) | Engineers, hiring managers | Every technology used and *why* it was chosen |
| [04 — Architecture](04-architecture.md) | Architects, reviewers | Components, data flows, and the reasoning behind the design |
| [05 — Data model](05-data-model.md) | Data / BI | The curated table, dimensions, and dashboard requirements |
| [06 — Automation & operations](06-automation-operations.md) | Ops, reviewers | How everything runs with no manual steps |
| [07 — Decision log](07-decision-log.md) | Architects, reviewers | Key decisions, the options weighed, and trade-offs accepted |
| [08 — Roadmap](08-roadmap.md) | Everyone | Phased build plan, each phase demo-able |
| [09 — Deployment troubleshooting](09-deployment-troubleshooting.md) | Ops, engineers | Every real deployment issue hit and how it was fixed |
| [devnotes](devnotes.md) | Engineers | Running per-task log of what was built and why |

## Design ethos in one line

Event-driven and schedule-driven, zero manual operations, one source of truth, and deliberately lean — a cost-optimisation tool that is itself cheap to run.
