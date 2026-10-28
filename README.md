# niava — Autonomous AI Agent with Persistent Memory

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Ollama](https://img.shields.io/badge/Ollama-local%20inference-000000?logo=ollama)](https://ollama.com)
[![Playwright](https://img.shields.io/badge/Playwright-browser%20automation-2EAD33?logo=playwright)](https://playwright.dev)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/Charcraft/niava/actions/workflows/ci.yml/badge.svg)](https://github.com/Charcraft/niava/actions)

> **Autonomous AI agent** with persistent memory (markdown facts + JSON), browser automation (Playwright/CDP), voice synthesis (ElevenLabs/edge-tts + Whisper STT), real social posting (Facebook Graph API), and extensible tool registry. Runs 100% local with Ollama.

---

## ✨ Features

| Capability | Implementation |
|------------|----------------|
| **Persistent Memory** | Markdown facts (`memory/`) + scheduled JSON reminders — survives restarts |
| **Brain** | Ollama (qwen2.5:3b/7b) + OmniRoute fallback; native endpoint, keep-alive |
| **Browser Automation** | Playwright + CDP (Chromium container) — real navigation, screenshots, form filling |
| **Voice** | TTS: ElevenLabs → edge-tts fallback; STT: ElevenLabs → local faster-whisper |
| **Social Posting** | Facebook Graph API — verified real posting to page (not user token) |
| **Tool Registry** | 13+ tools: file ops, web search, vision, voice, memory, self-improve, restart |
| **Vault/Graph** | Folder index → searchable graph (hubs, nodes, edges) |
| **Demo Mode** | `NIAVA_DEMO=1` for safe screen recording; `0` for real PC indexing (read-only) |
| **Streaming API** | SSE: `thinking`, `token`, `done` events for live UX |
| **Cost** | $0 local (Ollama + edge-tts + Whisper); ElevenLabs optional |

---

## 🿗️ Architecture

```
niava/
├── agent/
│   ├── main.py       # HTTP server + API + tool chaining + SSE streaming
│   ├── brain.py      # Ollama native + OmniRoute fallback
│   ├── vault.py      # Folder index → searchable graph
│   ├── tools.py      # 13 tools: FS, web, vision, voice, memory, self-improve
│   ├── data.py       # Only module touching real user data (read-only)
│   ├── vision.py     # On-demand screen capture
│   ├── voice.py      # TTS (ElevenLabs/edge-tts) + STT (Whisper)
│   ├── memory.py     # Persistent facts (markdown) + reminders (JSON)
│   ├── browser.py    # Playwright/CDP browser automation
│   ├── fbapi.py      # Facebook Graph API client
│   ├── social.py     # Social posting orchestration
│   ├── prompt.md     # System prompt
│   └── prompt.md     # System prompt
├── ui/               # Vanilla JS chat + graph + voice UI
├── memory/           # One .md per remembered fact
├── data/             # Demo fixtures
├── tests/            # pytest suite
└── docker-compose.yml
```

---

## 🚀 Quickstart

### Prerequisites
- Python 3.10+
- Ollama with `qwen2.5:3b` (or `nemotron3-ultra`) on `http://localhost:11434`
- NVIDIA GPU recommended (4GB VRAM for 3b)
- Optional: ElevenLabs API key for premium TTS

### Install
```bash
git clone https://github.com/Charcraft/niava
cd niava
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Install Playwright browsers
playwright install chromium
```

### Configure
```bash
cp .env.example .env
# Edit .env with your keys (ElevenLabs, Facebook, etc.)
```

### Run
```bash
# Demo mode (safe, fake data)
NIAVA_DEMO=1 python agent/main.py

# Real mode (indexes your PC read-only, filtered by your name)
NIAVA_DEMO=0 python agent/main.py
```

Open http://localhost:8010

---

## 🔧 Configuration (`.env`)

```env
# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_FALLBACK_MODEL=qwen2.5:7b

# OmniRoute (fallback)
OMNIROUTE_URL=http://localhost:20128

# Voice
ELEVENLABS_API_KEY=your_key_here  # optional, falls back to edge-tts

# Facebook Graph API (for social posting)
FB_PAGE_ID=your_page_id
FB_PAGE_ACCESS_TOKEN=your_page_token  # MUST be PAGE token, not user token
FB_GRAPH_VERSION=v19.0

# Demo mode
NIAVA_DEMO=1  # 1=demo, 0=real
```

---

## 🗡️ API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Chat with NIAVA (`{"message": "..."}`), SSE with `Accept: text/event-stream` |
| POST | `/api/speak` | TTS `{"text": "..."}` → MP3 |
| POST | `/api/listen` | STT (multipart audio) → transcription |
| POST | `/api/speak-listen` | Voice round-trip |
| GET | `/api/graph` | Knowledge graph (nodes + edges) |
| GET | `/api/status` | Ollama + OmniRoute health |
| GET | `/api/memory` | Remembered facts |
| GET | `/api/reminders` | Pending reminders |
| GET | `/api/hubs` | Graph hubs |

---

## 🧠 Memory System

- **Facts**: One `.md` file per fact in `memory/` — human-readable, versionable, grep-able
- **Reminders**: `scheduled_posts.json` for time-based actions
- **Graph**: `vault.py` indexes folders → hubs/nodes/edges for semantic navigation
- **Cross-session**: Survives restarts; loaded on startup

---

## 🌐 Browser Automation (Playwright + CDP)

- Connects to Chromium container (`ff-browser`) on CDP `127.0.0.1:9222`
- Real navigation, clicks, form fills, screenshots, HAR capture
- Session persistence (Google/TikTok login cookies in container profile)
- Human-like gestures via `human.py`

---

## 🕻️ Voice Pipeline

```
User voice → Whisper (local) → NIAVA brain → response → TTS (ElevenLabs/edge-tts) → audio.mp3
```

- STT: ElevenLabs Scribe → faster-whisper local fallback
- TTS: ElevenLabs v3 → edge-tts (free, multilingual) fallback
- Phonetic rewriting for Spanish (`diction.py`)

---

## 📈 Facebook Posting (Verified Real)

- Uses **Page Access Token** (not user token) — critical fix documented
- Posts to page feed with message + optional link/media
- Verified on page **CJEZP** (real production use)

---

## 🤪 Testing

```bash
# Unit tests
pytest tests/

# API integration test (requires running server)
pytest tests/test_api.py -v

# Lint
ruff check agent/
```

---

## 🐳 Docker (Optional)

```bash
docker-compose up -d
# Includes: niava-api, ollama, playwright-chromium
```

---

## 📁 Project Structure Details

<details>
<summary><b>agent/</b> — Core agent modules</summary>

| File | Responsibility |
|------|----------------|
| `main.py` | FastAPI server, API routes, tool chaining, SSE streaming |
| `brain.py` | Ollama client, prompt building, keep-alive, OmniRoute fallback |
| `vault.py` | Folder indexing → graph (hubs, nodes, edges), search |
| `tools.py` | 13 tools: list/read/write file, web search, vision, voice, memory, self-improve, restart |
| `data.py` | Single module accessing real user data (read-only, name-filtered) |
| `vision.py` | Screen capture on demand (mss) |
| `voice.py` | TTS/STT orchestration |
| `memory.py` | Persistent facts (markdown) + reminders (JSON) |
| `browser.py` | Playwright/CDP browser automation |
| `fbapi.py` | Facebook Graph API client |
| `social.py` | Social posting orchestration |
| `prompt.md` | System prompt |
</details>

<details>
<summary><b>ui/</b> — Frontend</summary>

Vanilla JS (no framework): chat interface, graph visualization (Cytoscape), voice controls, dark theme.
</details>

---

## 🤝 Contributing

1. Fork → branch → PR
2. Run `pytest` and `ruff check` before pushing
3. Update `AGENTS.md` if architecture changes
4. Follow `proveit` capability contract (run `proveit probe`)

---

## 📄 License

MIT © 2025 Carlos de Jesús Martínez Pineda ([Charcraft](https://github.com/Charcraft))

---

## 🔗 Related

- **Profile**: [github.com/Charcraft](https://github.com/Charcraft)
- **Landing**: [cxrlosmp-landing-z56q.vercel.app](https://cxrlosmp-landing-z56q.vercel.app/)
- **proveit**: [github.com/Charcraft/proveit](https://github.com/Charcraft/proveit)
- **tech-stack-advisor**: [github.com/Charcraft/tech-stack-advisor](https://github.com/Charcraft/tech-stack-advisor)

---

*Built with real problems → real solutions. No tutorials, just production code.*