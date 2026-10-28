# Agent Instructions for niava

This repository contains **niava** — an autonomous AI agent with persistent memory, browser automation, voice, and real social posting.

## Development

- **Main branch**: `main`
- **Python**: 3.10+ (see `.python-version` or `requirements.txt`)
- **Virtual env**: `.venv/` (gitignored)
- **Run**: `NIAVA_DEMO=1 python agent/main.py` (demo) or `NIAVA_DEMO=0 python agent/main.py` (real)

## Capability Contract (proveit)

Run before claiming environment limitations:

```bash
npx github:Charcraft/proveit probe --browser
npx github:Charcraft/proveit prompt --write AGENTS.md
```

## Agent Protocol (OpenCode)

When working in this repo:
1. Read `AGENT_CONTEXT` if present (decisions, architecture, state)
2. Update `AGENT_CONTEXT` after significant changes
3. Run `proveit probe` before claiming limitations
4. All PRs require: `proveit probe` green + `pytest` passing + `ruff check` clean

## Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| Single `data.py` for real PC access | Audit surface minimized; read-only; name-filtered |
| Markdown facts for memory | Human-readable, versionable, grep-able, no DB needed |
| Playwright + CDP (not Selenium) | Modern, reliable, CDP gives full Chrome control |
| Page Access Token for FB | User tokens cannot post to pages — learned the hard way |
| Demo mode flag | Safe screen recording without exposing real data |
| SSE streaming | Live UX: thinking → token → done |

## Subagents to Use

- `backend-architect` — API design, FastAPI patterns
- `ai-engineer` — Ollama integration, prompt engineering
- `devops-automator` — Docker, Playwright container setup
- `code-reviewer` — Security (tokens, PC access), performance
- `privacy-engineer` — Data minimization, consent, deletion

## Critical Files to Understand

- `agent/main.py` — Entry point, API, tool orchestration
- `agent/tools.py` — Tool registry (add tools here)
- `agent/memory.py` — Persistence layer
- `agent/brain.py` — LLM client logic
- `agent/browser.py` — Browser automation
- `agent/fbapi.py` — Facebook posting (token handling!)

## Testing Checklist

- [ ] `pytest tests/` passes
- [ ] `ruff check agent/` clean
- [ ] Demo mode runs: `NIAVA_DEMO=1 python agent/main.py`
- [ ] API responds: `curl -X POST localhost:8010/api/chat -d '{"message":"hola"}'`
- [ ] Memory persists across restarts
- [ ] No secrets in code (check `.env` gitignored)

## Secrets Management

- `.env` → gitignored, never commit
- `fb_config.json` → gitignored, contains FB tokens
- `chrome-profile/` → gitignored, browser session data
- Use `vault.py` for any future secret storage