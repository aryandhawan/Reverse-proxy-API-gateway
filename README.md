# 📡 High-Availability AI Proxy Gateway

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)
![Docker](https://img.shields.io/badge/Docker-Multi--Container-2496ED.svg)
![Azure](https://img.shields.io/badge/Azure-Cloud_Deployed-0089D6.svg)
![Redis](https://img.shields.io/badge/Redis-Rate_Limiting-DC382D.svg)

An enterprise-grade, fault-tolerant AI API Gateway designed to route inference requests with zero-latency failovers. This project was built with a heavy emphasis on **MLOps, infrastructure resilience, and edge security**, moving beyond standard product features to implement a true production-ready deployment architecture.

By default, the gateway routes traffic through high-speed **Groq LPUs**. If Groq experiences downtime or rate limits, the gateway's proactive circuit breaker instantly re-routes traffic to **Google Gemini**, ensuring 100% uptime for end-users.

---

## ✨ Architectural Highlights & MLOps Focus

While the application code is built in FastAPI, the core focus of this project is its distributed systems architecture and deployment pipeline.

### 🛡️ Edge Security & Rate Limiting
To protect downstream LLM API keys from abuse, the gateway sits behind a custom distributed rate limiter. 
* Uses **Redis `INCR`** operations tied to client IP addresses.
* Enforces strict Time-To-Live (TTL) penalty boxes to automatically block malicious actors or runaway scripts before they reach the LLM execution layer.

### 💓 Proactive Circuit Breaker (Self-Healing LLM Routing)
Unlike passive systems that wait for a user's request to fail, this gateway features an **Active Health Monitor**.
* An asynchronous background worker continuously pings the primary **Groq** API.
* If a ping fails, the worker immediately updates the LLM health status in **Redis** to `DOWN` with a 60-second TTL.
* **Zero-Latency Failover:** Subsequent user requests check Redis *first*. Seeing the `DOWN` status, the proxy engine instantly reroutes the payload to the secondary fallback (**Google Gemini**) without waiting for a timeout, completely shielding the user from the cloud provider's outage.

### 📊 Asynchronous Telemetry
* Execution latency, routed provider, and HTTP status codes are written to a **PostgreSQL** database.
* To prevent database writes from slowing down user responses, telemetry is handled entirely via FastAPI `BackgroundTasks` after the HTTP response has already been sent.

### ☁️ Cloud Orchestration & SSL
* **Multi-Container Docker:** The entire stack (FastAPI, Streamlit Dashboard, PostgreSQL, Redis) is containerized and orchestrated via `docker-compose`.
* **Azure Cloud:** Deployed on Microsoft Azure services to simulate a real-world scalable environment.
* **Caddy Reverse Proxy:** Implemented **Caddy** at the edge to handle automated SSL/TLS certificate generation and HTTPS termination, securing the payload in transit.

---

## 🛠️ Tech Stack

* **API Gateway:** FastAPI, Uvicorn/Gunicorn, Python `asyncio`
* **Primary LLM Engine:** Groq (`llama-3.1-8b`, `llama-3.3-70b`)
* **Secondary LLM Engine:** Google Gemini (`gemini-2.5-flash`)
* **State & Caching:** Redis
* **Data Persistence:** PostgreSQL
* **Observability Dashboard:** Streamlit, Pandas, Psycopg2
* **Infrastructure / Deployment:** Docker, Docker Compose, Caddy (SSL), Microsoft Azure

---

## 🚀 The Observability Dashboard

This repository includes a fully containerized **Command Center (Streamlit)** for real-time system monitoring. It provides:
1. **Interactive Console:** Send configurable JSON payloads directly to the gateway.
2. **Chaos Engineering Toggle:** Intentionally simulate a primary provider crash to watch the circuit breaker trip and reroute to Gemini in real-time.
3. **Stress Testing:** Rapidly fire requests to validate the Redis rate-limiting logic.
4. **Telemetry Analytics:** Live time-series charts visualizing overhead latency and model distribution pulled directly from PostgreSQL.

---

## 💻 Local Development Setup

To run the entire multi-container architecture locally:

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/yourusername/ai-proxy-gateway.git](https://github.com/yourusername/ai-proxy-gateway.git)
   cd ai-proxy-gateway

  ## 🧠 Lessons Learned
This project served as a deep dive into MLOps and backend architecture. It reinforced the idea that connecting to an AI model is easy, but building the infrastructure to protect, scale, and monitor that model is where true engineering happens.
