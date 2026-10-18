# No-Code Agent

A modern, full-stack platform for visually building, testing, and deploying intelligent AI workflows and autonomous agents without writing code.

---

## 🚀 Overview

**No-Code Agent** empowers developers and non-technical creators to design complex agentic workflows using an intuitive visual graph interface. Connect LLMs, tools, memory, conditional logic, and eval suites with drag-and-drop simplicity.

### Key Features

- **Visual Workflow Builder**: Interactive node-based canvas powered by React and `@xyflow/react`.
- **FastAPI Backend**: Asynchronous REST & SSE API with Python 3, MongoDB, and Redis caching.
- **Microservices Architecture**: Full Docker Compose stack with Nginx reverse proxy, MongoDB, and Redis.
- **Extensible Agent Components**: Nodes for prompts, memory, compiler, evals, and runtime execution.
- **Secure Authentication**: Built-in JWT authentication and environment credential handling.

---

## 🛠️ Tech Stack

- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS, `@xyflow/react`, Lucide Icons, Zustand
- **Backend**: Python FastAPI, Motor (Async MongoDB), Redis, Pydantic v2, Python-JOSE
- **Database & Cache**: MongoDB 7, Redis 7 Alpine
- **Proxy**: Nginx Alpine

---

## 📦 Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/)
- [Node.js](https://nodejs.org/) (v18+) & [Python](https://www.python.org/) (v3.10+) for local development without Docker

### 1. Clone the Repository

```bash
git clone https://github.com/AbhishekC1005/No-Code-Agent.git
cd No-Code-Agent
```

### 2. Configure Environment Variables

Copy the example environment configuration:

```bash
cp .env.example .env
```

Edit `.env` to configure your credentials:
```env
MONGO_USER=admin
MONGO_PASS=your_secure_password
JWT_SECRET=your_random_64_character_secret
REDIS_URL=redis://redis:6379/0
```

### 3. Run with Docker Compose

Launch the entire stack (Frontend, Backend, MongoDB, Redis, and Nginx) with a single command:

```bash
docker-compose up --build
```

The application will be accessible at:
- **Frontend / Application**: [http://localhost](http://localhost)
- **API Documentation (Swagger)**: [http://localhost/docs](http://localhost/docs)
- **FastAPI Direct**: [http://localhost:8000](http://localhost:8000)

---

## 💻 Local Development

### Backend

```bash
cd backend
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server will run at [http://localhost:5173](http://localhost:5173).

---

## 📂 Project Structure

```
.
├── backend/            # FastAPI Python backend
│   ├── app/            # Application logic, routes, and models
│   ├── Dockerfile      # Backend container definition
│   └── requirements.txt# Python dependencies
├── frontend/           # React + Vite TypeScript frontend
│   ├── src/            # Components, runtime, evals, and UI
│   ├── Dockerfile      # Frontend container definition
│   └── package.json    # Frontend dependencies
├── nginx/              # Nginx reverse proxy configuration
│   └── nginx.conf
├── docker-compose.yml  # Docker multi-container specification
├── .env.example        # Environment variable template
└── README.md           # Project documentation
```

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).
