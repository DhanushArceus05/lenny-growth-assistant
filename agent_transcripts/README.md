# Agent Transcripts

This folder preserves logs of the coding-agent (Claude) sessions used to build this
project, per the assignment's deliverable #6 — including corrections and failed
attempts, not just a polished final diff.

## What's here

- `01_initial_scaffolding_and_backend.md` — the first implementation session: repo
  scaffolding, docs, backend (config, providers, RAG, skills, API, tests), including
  the environment issues hit and how they were resolved.
- `02_frontend_and_deployment.md` — the second session: frontend components, Docker
  Compose, README, and final verification.

## Rules for adding to this folder

- **Never commit secrets.** Before adding a transcript, grep it for anything that
  looks like an API key, password, or connection string with real credentials, and
  redact with `<REDACTED>` if found. The transcripts in this repo were generated
  against placeholder config only, but this is still worth checking on every export.
- Keep failed attempts and corrections in, not just the final successful state — the
  value of this folder for a handoff is seeing *how* problems were diagnosed and
  fixed (e.g., the tiktoken network-dependency issue below), not a rewritten history.
- Name new transcripts `NN_short_description.md` in chronological order.
