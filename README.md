# 🏏 IPL Live Tracker — Containerized Microservice

![Docker](https://img.shields.io/badge/docker-containerized-blue)
![CI/CD](https://img.shields.io/badge/CI/CD-GitHub%20Actions-green)
![Platform](https://img.shields.io/badge/platform-linux%20amd64%20%7C%20arm64-orange)

A containerized microservice that fetches live IPL cricket match data and displays it in a browser. Built to demonstrate modern DevOps engineering practices using Docker, Redis, GitHub Actions, and Google Cloud Platform.

---

## 📌 Table of Contents

- [Demo](#demo)
- [DevOps Highlights](#devops-highlights)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Application Workflow](#application-workflow)
- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Running the Project](#running-the-project)
- [Docker Concepts Demonstrated](#docker-concepts-demonstrated)
- [CI/CD Pipeline](#cicd-pipeline)
- [Cloud Deployment (GCP)](#cloud-deployment-gcp)
- [Observability and Monitoring](#observability-and-monitoring)
- [Security Considerations](#security-considerations)
- [Future Improvements](#future-improvements)

---

## 🌐 Demo

> Deploy the app locally or on GCP using the steps below.  
> Once running, open your browser at:

```
http://localhost:5000         # local
http://<your-gcp-ip>:5000    # GCP deployment
```

---

## ⚙️ DevOps Highlights

This project demonstrates several production-grade DevOps engineering practices:

- Containerized microservice architecture
- Multi-stage Docker image builds for smaller, more secure images
- Multi-architecture image support (`amd64` / `arm64`)
- Non-root container user for improved security
- Redis-based caching layer with AOF persistence enabled
- Infrastructure isolation using Docker networks
- Persistent storage using Docker volumes
- Healthcheck-based service dependency (`depends_on: condition: service_healthy`)
- Environment variable based secrets management
- CI/CD pipeline using GitHub Actions
- Automated DockerHub image publishing
- Cloud deployment to Google Cloud Platform (Compute Engine)

---

## 🏗️ Architecture

The system consists of two containers communicating over an isolated Docker network:

```
                +-------------------+
                |   User Browser    |
                | http://IP:5000    |
                +---------+---------+
                          |
                     Docker Network
                    (ipl-network)
                          |
         +----------------+----------------+
         |                                 |
 +-------v--------+                 +------v-------+
 | Flask App      |   redis-cli     | Redis Cache  |
 | IPL Tracker    | <------------>  | visitor data |
 | Gunicorn WSGI  |                 | API caching  |
 +-------+--------+                 +------+-------+
                                           |
                                    Docker Volume
                                  (redis-data / AOF)
```

- **Flask + Gunicorn** — serves the IPL UI and handles API requests
- **Redis** — caches live API responses (45s TTL) and tracks visitor metrics
- **Redis is not exposed publicly** — accessible only within the Docker network

---

## 📁 Project Structure

```
ipl-live-tracker/
│
├── main.py                # Flask application
├── requirements.txt       # Pinned Python dependencies
├── Dockerfile             # Multi-stage Docker build
├── docker-compose.yml     # Container orchestration
├── .env                   # Environment variables (not committed)
├── .dockerignore          # Excludes secrets and junk from image
└── README.md
```

---

## 🔄 Application Workflow

1. User opens the application in the browser
2. Flask (via Gunicorn) receives the incoming request
3. Redis is checked for a cached IPL API response
4. If the cache is empty or expired, the app fetches fresh data from the cricket API
5. Redis stores the response for **45 seconds** to reduce external API calls
6. The UI displays:
   - Live IPL scores and match status
   - Total page views
   - Unique visitor count

---

## ✅ Prerequisites

Before running this project, ensure you have the following installed:

| Tool | Minimum Version | Install |
|---|---|---|
| Docker | 24.x | [docs.docker.com](https://docs.docker.com/get-docker/) |
| Docker Compose | 2.x | Included with Docker Desktop |
| Cricket API Key | — | [cricketdata.org](https://cricketdata.org) or your preferred provider |

---

## 🔐 Environment Variables

Create a `.env` file in the project root. **Never commit this file to version control.**

```env
CRICKET_API_KEY=your_api_key_here
REDIS_HOST=redis
```

The API key is injected at runtime through environment variables and is never baked into the Docker image.

---

## 🚀 Running the Project

**Clone the repository:**

```bash
git clone https://github.com/<your-username>/ipl-live-tracker.git
cd ipl-live-tracker
```

**Create your `.env` file:**

```bash
cp .env.example .env
# then edit .env and add your CRICKET_API_KEY
```

**Build and start the containers:**

```bash
docker compose up --build
```

**Open in your browser:**

```
http://localhost:5000
```

**Stop the containers:**

```bash
docker compose down
```

**Stop and remove volumes (resets Redis data):**

```bash
docker compose down -v
```

---

## 🐳 Docker Concepts Demonstrated

### Multi-Stage Build

The `Dockerfile` separates dependency installation from the runtime image:

- **Stage 1 (builder):** installs all Python packages using `pip install --user`
- **Stage 2 (runtime):** copies only the installed packages into a clean, minimal image

Benefits: smaller image size, faster deployments, reduced attack surface.

### Non-Root User

The container runs as a non-root `appuser` to follow the principle of least privilege.

### Docker Network

Both containers share an isolated Docker network (`ipl-network`).

```
ipl-tracker  →  redis (internal DNS)
```

Redis is not exposed on any host port — it is only reachable within the container network.

### Docker Volume

A named volume (`redis-data`) persists Redis data across container restarts.

Combined with `--appendonly yes` (AOF persistence), this ensures:

- Visitor counts survive container restarts
- Cached data is written to disk reliably

### Healthcheck + depends_on

The Flask container waits for Redis to be **fully ready** (not just started) before launching:

```yaml
depends_on:
  redis:
    condition: service_healthy
```

This eliminates the race condition where Flask starts before Redis is accepting connections.

### Multi-Architecture Build

The image supports multiple CPU architectures:

- `linux/amd64` — standard Intel/AMD servers
- `linux/arm64` — AWS Graviton, ARM cloud instances, Apple M1/M2

**Build and push a multi-arch image:**

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t <dockerhub-user>/ipl-tracker:latest \
  --push .
```

---

## 🔁 CI/CD Pipeline

The project integrates with GitHub Actions for automated builds and image publishing.

**Pipeline workflow:**

```
Developer pushes code to GitHub
        ↓
GitHub Actions triggered
        ↓
Docker Buildx builds multi-arch image (amd64 + arm64)
        ↓
Image pushed to DockerHub
        ↓
Deployment environment pulls latest image
```

This ensures consistent, automated, and reproducible container builds on every push.

**Example GitHub Actions workflow file:** `.github/workflows/docker-publish.yml`

```yaml
name: Build and Push Docker Image

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to DockerHub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          push: true
          platforms: linux/amd64,linux/arm64
          tags: <dockerhub-user>/ipl-tracker:latest
```

---

## ☁️ Cloud Deployment (GCP)

The application can be deployed on a Google Cloud Platform Compute Engine VM.

**Basic deployment steps:**

1. Create a Compute Engine VM (e2-micro or larger)
2. Install Docker on the VM
3. Pull the image from DockerHub
4. Run the container with required environment variables

```bash
# On the GCP VM
docker run -d \
  -p 5000:5000 \
  -e CRICKET_API_KEY=<your_api_key> \
  -e REDIS_HOST=redis \
  --name ipl-tracker \
  <dockerhub-user>/ipl-tracker:latest
```

> **Note:** For production use, run both containers using `docker compose` on the VM rather than individual `docker run` commands so Redis is available on the internal network.

---

## 📊 Observability and Monitoring

In a production environment, this application can be extended with:

- **Prometheus** — metrics collection (request count, latency, Redis hits/misses)
- **Grafana** — dashboards for visualising metrics
- **ELK Stack** — centralised log aggregation (Elasticsearch, Logstash, Kibana)
- **Health check endpoints** — `/health` route for load balancer probes

---

## 🔒 Security Considerations

The project follows standard container security practices:

- API keys injected through environment variables — never stored in the image
- `.env` file excluded from the Docker image via `.dockerignore`
- `.git` history and source secrets excluded from image layers
- Redis not exposed on any public port — isolated to the Docker network
- Application runs as a non-root user (`appuser`) inside the container
- Gunicorn used as WSGI server — Flask dev server not used in production

---

## 🔮 Future Improvements

- Kubernetes deployment on GKE with Horizontal Pod Autoscaler
- Nginx reverse proxy for SSL termination
- HTTPS using Let's Encrypt / Cert Manager
- Monitoring with Prometheus and Grafana
- Structured JSON logging
- `/health` endpoint for liveness and readiness probes
- Helm chart for GKE deployment

---

## 📄 License

This project is for demonstration and learning purposes.
