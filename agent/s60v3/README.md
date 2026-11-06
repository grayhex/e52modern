# SymPort Device Agent for S60v3 — not built

This directory is intentionally without source or binaries. Building the phone-side agent needs the
S60 3rd Edition SDK (FP1 for the N95, FP2 for the E52/E72), signing and a real phone. The host side and
the protocol are in `symport/agent/` and documented in `docs/AGENT.md`; the manual checklist is in
`CHECKLIST.md`. A SIS must pass the Inspector (structure, capabilities, platform UID) before any test.
