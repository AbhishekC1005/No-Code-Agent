# No-Code Agent

An n8n-style visual AI agent and workflow builder (React + @xyflow/react frontend, FastAPI backend) that runs locally on your machine with **one command** — zero Docker, MongoDB, or Redis required.

All workflows, execution history, and encrypted credentials are automatically stored locally in a single SQLite database at `~/.nocode-agent/data.db`.

---

## ⚡ Quick Start (One Command)

### 1. Install & Run via pip

```bash
# Clone the repository
git clone https://github.com/AbhishekC1005/No-Code-Agent.git
cd No-Code-Agent

# Install dependencies and CLI
pip install -e .

# Launch No-Code Agent (starts server and opens your browser)
nocode-agent start
```

That's it! Your browser will automatically open to `http://127.0.0.1:8000`.

---

## 🐳 Docker Option (Single Container)

If you prefer running via Docker, a single self-contained multi-stage container is available:

```bash
# Build the single container
docker build -t nocode-agent .

# Run with persistent volume for your local workflows
docker run -p 8000:8000 -v nocode_data:/data nocode-agent
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## 🛠️ CLI Options

```bash
nocode-agent start [OPTIONS]

Options:
  --port INTEGER    Port to listen on (default: 8000)
  --host TEXT       Host interface to bind to (default: 127.0.0.1)
  --no-browser      Do not automatically launch the default browser
  --help            Show help message
```

---

## ⚙️ Configuration & Environment Variables

No-Code Agent works out of the box with zero configuration. You can customize runtime settings via environment variables:

| Variable | Default | Description |
|---|---|---|
| `NOCODE_DATA_DIR` | `~/.nocode-agent` | Directory where SQLite database (`data.db`) and secret keys are stored |
| `AUTH_ENABLED` | `false` | When `false`, runs in single-user local mode without login. Set to `true` to require multi-user JWT authentication. |
| `OPENAI_API_KEY` | *(empty)* | Optional default OpenAI API key (can also be configured via in-app Vault) |
| `ANTHROPIC_API_KEY` | *(empty)* | Optional default Anthropic API key (can also be configured via in-app Vault) |
| `PINECONE_API_KEY` | *(empty)* | Optional default Pinecone API key |

---

## 🏗️ Building from Source

To compile the React frontend and package it into the backend:

```bash
python build.py
```

Or using Make:
```bash
make build
```

---

## 💻 Development Mode

For local development with hot-reloading:

1. **Frontend dev server (Vite with HMR):**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Runs at [http://localhost:5173](http://localhost:5173) with automatic proxying to backend on port 8000.

2. **Backend dev server (Uvicorn with auto-reload):**
   ```bash
   uvicorn nocode_agent.main:app --reload --port 8000
   ```

---

## 📁 Architecture

- **Embedded SQLite Engine**: Stored at `~/.nocode-agent/data.db` using `aiosqlite`. Manages tables for users, workspaces (nodes, edges, schemas as JSON), encrypted credentials, and execution logs.
- **Unified Single-Process Server**: FastAPI hosts the REST API, SSE execution stream, and serves the compiled React SPA static assets.
- **Local Credential Vault**: Auto-generates a cryptographic secret on first run (`~/.nocode-agent/secret.key`) and uses Fernet symmetric encryption for all API keys.
- **Visual Canvas**: Drag-and-drop workflow designer powered by `@xyflow/react` with 9 node categories: Triggers, Models, Agents, Tools, Memory, Knowledge, Logic, Output, and Plugins.

---

## 📄 License

MIT License.
