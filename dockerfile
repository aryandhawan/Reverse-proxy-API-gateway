# 1. THE BASE (The Operating System)

FROM python:3.11-slim

# 2. THE WORKSPACE
# This creates a folder inside the container called /app and moves us into it.
WORKDIR /app

# 3. THE CACHE OPTIMIZATION (Crucial Step)
# Docker skips the slow 'pip install' step and builds your image instantly.
COPY requirements.txt .

# 4. THE INSTALLATION 
# it keeps our final container size as tiny as possible.
RUN pip install --no-cache-dir -r requirements.txt

# 5. THE CODE
# Now we copy the rest of your actual Python files (main.py, etc.) into the container.
COPY . .

# 6. THE EXPOSURE
# This is documentation for developers, letting them know this container expects traffic on 8000.
EXPOSE 8000

# 7. THE PRODUCTION RUNNER
# We tell Gunicorn to run 'main:app'. 
# -w 4: Spin up 4 Uvicorn workers.
# -k: Use the Uvicorn worker class (since FastAPI requires async).
# --bind: Listen on port 8000 so the outside world (and Docker Compose) can talk to it.
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]