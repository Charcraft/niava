# CLAUDE.md — niava

## Project Overview

**niava** — Autonomous AI agent with persistent memory, browser automation, voice synthesis, and real social posting. Runs 100% local with Ollama.

## Commands

```bash
# Demo mode (safe)
NIAVA_DEMO=1 python agent/main.py

# Real mode (read-only PC indexing)
NIAVA_DEMO=0 python agent/main.py

# Tests
pytest tests/

# Lint
ruff check agent/

# Type check (optional)
mypy agent/

# ProveIt capability probe
npx github:Charcraft/proveit probe --browser
npx github:Charcraft/proveit prompt --write AGENTS.md
```

## Development Rules

1. **Single data access point**: Only `agent/data.py` touches real user files (read-only, name-filtered)
2. **Memory = Markdown + JSON**: `memory/` for facts, `scheduled_posts.json` for reminders
3. **Browser = Playwright + CDP**: Connect to `ff-browser` container on `127.0.0.1:9222`
4. **Voice = ElevenLabs → edge-tts fallback**: STT = ElevenLabs → faster-whisper fallback
5. **FB posting = Page Token only**: User tokens fail; verified on page CJEZP
6. **Demo mode flag**: `NIAVA_DEMO=1` for safe recording; `0` for real indexing
7. **No secrets in code**: `.env`, `fb_config.json`, `chrome-profile/` all gitignored

## Agent Instructions

- Use `backend-architect` for API/FastAPI changes
- Use `ai-engineer` for LLM/Ollama/prompt changes
- Use `devops-automator` for Docker/Playwright/container changes
- Use `code-reviewer` + `privacy-engineer` for security review (PC access, tokens)
- Run `proveit probe` before any "I cannot" claim
- Update `AGENT_CONTEXT` after architectural decisions

## Key Files

| File | Purpose |
|------|---------|
| `agent/main.py` | FastAPI server, SSE streaming, tool chaining |
| `agent/tools.py` | Tool registry (13 tools) |
| `agent/brain.py` | Ollama client, keep-alive, fallback |
| `agent/memory.py` | Persistent facts + reminders |
| `agent/browser.py` | Playwright/CDP automation |
| `agent/fbapi.py` | Facebook Graph API (PAGE token!) |
| `agent/vault.py` | Folder → graph indexing |
| `agent/voice.py` | TTS/STT orchestration |
| `ui/` | Vanilla JS frontend |

## Testing Requirements

- All PRs: `pytest` + `ruff` + `proveit probe` green
- Demo mode must start and serve UI at `localhost:8010`
- Memory persistence verified across restart
- No hardcoded secrets anywhere

## Deployment

- Local: `python agent/main.py`
- Docker: `docker-compose up -d` (includes Ollama + Chromium)
- VPS: systemd service + reverse proxy

## Related Repos

- Profile: [Charcraft/Charcraft](https://github.com/Charcraft/Charcraft)
- Landing: [Charcraft/CXRLOSMP-LANDING](https://github.com/Charcraft/CXRLOSMP-LANDING)
- proveit: [Charcraft/proveit](https://github.com/Charcraft/proveit)