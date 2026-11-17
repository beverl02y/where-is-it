# CLAUDE.md — Where-Is-It AI

> The only file Claude Code reads automatically when a session starts in this repository.
> Rules, glossary and operating information are all in `AGENTS.md`; this file only imports it, so every tool reads the same document. Do not copy rules here.

@AGENTS.md

## Only for Claude Code
- Load check: in a new session run `/context` — both `CLAUDE.md` and `AGENTS.md` should be listed. `docs/SPEC.md` and `docs/ontology.yaml` are read on request, so it is normal that they are not listed.
