# VLLM Cluster Dashboard

A modern web dashboard for managing VLLM (Very Large Language Model) inference clusters. Features real-time monitoring, model management, benchmark testing, remote deployment, and AI-assisted operations.

![Tech Stack](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![Docker](https://img.shields.io/badge/Docker-✓-2496ED?logo=docker)
![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6?logo=typescript)
![License](https://img.shields.io/badge/License-MIT-green)

## Features

### Cluster Management
- Multi-node cluster orchestration
- GPU monitoring and utilization tracking
- Auto-scaling with configurable policies
- Federated learning support

### Model Management
- Model deployment, scaling, and lifecycle management
- HuggingFace & ModelScope model download (local + remote)
- Model marketplace with pre-configured templates
- Model version tracking

### Benchmark & Testing
- Performance benchmarking (throughput, latency, tokens/sec)
- A/B testing framework
- Real-time benchmark progress tracking
- Cost analysis and optimization reports

### AI Assistant
- Built-in AI chat interface for natural language cluster operations
- Streaming responses with tool-call execution
- Sidebar panel design (slide-in from right)

### Operations
- Log viewer with real-time streaming
- Audit trail and security logs
- Notification center
- Remote deployment to GPU servers via SSH

## Tech Stack

| Layer    | Technology                           |
| -------- | ------------------------------------ |
| Backend  | FastAPI, Python 3.11+, Docker SDK    |
| Frontend | React 18, TypeScript, Tailwind CSS   |
| UI       | Framer Motion, Recharts, Lucide Icons|
| Infra    | Docker, Docker Compose, Nginx        |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- GPU node(s) with NVIDIA drivers (for inference workloads)

### Run with Docker Compose

```bash
git clone https://github.com/your-username/vllm-dashboard.git
cd vllm-dashboard
docker compose up -d
```

The dashboard will be available at:

- **Web UI**: http://localhost
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs

### Development Mode

**Backend**:

```bash
cd backend
pip install -r requirements.txt
python main.py
```

**Frontend**:

```bash
cd frontend
npm install
npm run dev
```

The dev frontend runs at http://localhost:5173.

## Configuration

Configuration is managed through `backend/config.py` and can be overridden by:

- Environment variables (supports `.env` file)
- Persistent settings via the Web UI (Settings page)

Key settings:

| Variable                      | Default                    | Description                |
| ----------------------------- | -------------------------- | -------------------------- |
| `ray_image`                   | `rayproject/ray:latest`    | Ray cluster image          |
| `vllm_image`                  | `vllm/vllm-openai:latest`  | VLLM inference image       |
| `default_model_path`          | `/models`                  | Model storage path         |
| `default_gpu_memory_utilization` | `0.90`                  | GPU memory fraction        |

## Project Structure

```
vllm-dashboard/
├── backend/
│   ├── api/            # REST API endpoints
│   ├── services/       # Business logic & integrations
│   ├── config.py       # Application configuration
│   ├── main.py         # FastAPI application entry
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/ # Reusable UI components
│   │   ├── pages/      # Page-level components
│   │   ├── hooks/      # Custom React hooks
│   │   └── types/      # TypeScript type definitions
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
└── docker-compose.yml
```

## API Overview

| Endpoint             | Description              |
| -------------------- | ------------------------ |
| `/api/clusters`      | Cluster management       |
| `/api/models`        | Model lifecycle          |
| `/api/benchmarks`    | Benchmark execution      |
| `/api/settings`      | System settings          |
| `/api/download`      | Model download (local/remote) |
| `/api/marketplace`   | Model marketplace        |
| `/api/ai`            | AI assistant             |
| `/api/gpu`           | GPU monitoring           |
| `/api/dashboard`     | Dashboard aggregations   |
| `/api/logs`          | Log streaming            |
| `/api/features`      | Feature flags & A/B test |
| `/api/status`        | Health & status          |

Full API documentation available at `/api/docs` after startup.

## License

MIT License - see [LICENSE](LICENSE) for details.
