# Backend Dockerfile — builds the FastAPI image.
#
# Base: python:3.11-slim — small (~120MB), official, has Python 3.11.
# We use 3.11 specifically (not 3.12) because some scientific libs
# (cvxpy, numpy) sometimes lag behind the latest Python release.

FROM python:3.11-slim

# Working directory inside the container. All subsequent paths are
# relative to /app.
WORKDIR /app

# System dependencies needed for some Python packages:
#   - build-essential: gcc/make, needed by psycopg2-binary on some platforms
#   - libpq-dev: PostgreSQL client headers, also for psycopg2
# We clean up apt cache afterward to keep the image small.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (before the source code) so Docker can cache
# the pip install layer. If only source code changes, pip install is
# skipped — much faster rebuilds.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the backend source.
COPY . .

# Expose the FastAPI port. This is documentation only; docker-compose
# does the actual port mapping.
EXPOSE 8000

# Default command (can be overridden by docker-compose). Used when
# running the image standalone.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
