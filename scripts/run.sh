#!/usr/bin/env bash
set -e

# ─────────────────────────────────────────────────
# Portfolio Builder — Full Setup & Run Script
# Backend stack runs in Docker (avoids local
# Python build issues with cvxpy/ecos on macOS arm64).
# Frontend runs locally for fast iteration.
# ─────────────────────────────────────────────────

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

step() { echo -e "\n${BLUE}━━━ $1 ━━━${NC}"; }
ok()   { echo -e "${GREEN}✔ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
fail() { echo -e "${RED}✘ $1${NC}"; exit 1; }

# ─────────────────────────────────────────────────
# 1. Prerequisites
# ─────────────────────────────────────────────────
step "Checking prerequisites"
command -v docker >/dev/null 2>&1 || fail "Docker is not installed"
command -v node >/dev/null 2>&1   || fail "Node.js is not installed"
command -v npm >/dev/null 2>&1    || fail "npm is not installed"
ok "docker $(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"
ok "node $(node --version)"

# ─────────────────────────────────────────────────
# 2. .env
# ─────────────────────────────────────────────────
step "Setting up environment"
if [ ! -f .env ]; then
    cp .env.example .env
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/change-me-in-production/$SECRET_KEY/" .env
    else
        sed -i "s/change-me-in-production/$SECRET_KEY/" .env
    fi
    ok "Created .env with generated SECRET_KEY"
else
    ok ".env already exists"
fi

# ─────────────────────────────────────────────────
# 3. Build & start backend stack in Docker
# ─────────────────────────────────────────────────
step "Building and starting Docker stack (db, redis, backend, celery)"
docker compose up -d --build
ok "All containers up"

echo -n "Waiting for PostgreSQL..."
for i in $(seq 1 30); do
    if docker compose exec -T db pg_isready -U portfolio >/dev/null 2>&1; then
        echo ""
        ok "PostgreSQL is ready"
        break
    fi
    echo -n "."
    sleep 1
    if [ "$i" -eq 30 ]; then
        echo ""
        fail "PostgreSQL did not become ready in time"
    fi
done

# ─────────────────────────────────────────────────
# 4. Migrations
# ─────────────────────────────────────────────────
step "Running database migrations"
if [ -z "$(ls -A backend/alembic/versions/ 2>/dev/null)" ]; then
    docker compose run --rm backend alembic revision --autogenerate -m "initial schema"
    ok "Generated initial migration"
fi
docker compose run --rm backend alembic upgrade head
ok "Database schema up to date"

# Restart backend so startup seed runs after migrations
docker compose restart backend >/dev/null
ok "Backend restarted"

# ─────────────────────────────────────────────────
# 5. Frontend
# ─────────────────────────────────────────────────
step "Setting up frontend"
cd "$ROOT_DIR/frontend"
if [ ! -d "node_modules" ]; then
    npm install
    ok "Frontend dependencies installed"
else
    ok "Frontend dependencies already installed"
fi

# Kill anything on the frontend port
lsof -ti:5173 2>/dev/null | xargs kill -9 2>/dev/null || true

step "Starting frontend dev server"
npm run dev &
FRONTEND_PID=$!
ok "Frontend starting on http://localhost:5173 (PID: $FRONTEND_PID)"

# ─────────────────────────────────────────────────
# 6. Wait for backend health
# ─────────────────────────────────────────────────
cd "$ROOT_DIR"
echo -n "Waiting for backend..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        echo ""
        ok "Backend is ready"
        break
    fi
    echo -n "."
    sleep 1
    if [ "$i" -eq 30 ]; then
        echo ""
        warn "Backend did not respond — check: docker compose logs backend"
    fi
done

# ─────────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Portfolio Builder is running!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  Frontend:  ${BLUE}http://localhost:5173${NC}"
echo -e "  Backend:   ${BLUE}http://localhost:8000${NC}"
echo -e "  API Docs:  ${BLUE}http://localhost:8000/docs${NC}"
echo -e "  Database:  ${BLUE}localhost:5434${NC}  (postgres in docker)"
echo -e "  Redis:     ${BLUE}localhost:6379${NC}"
echo ""
echo -e "  Logs:    ${YELLOW}docker compose logs -f backend${NC}"
echo -e "  Stop:    ${YELLOW}./scripts/stop.sh${NC}"
echo -e "  Press   ${YELLOW}Ctrl+C${NC} to stop the frontend (containers keep running)"
echo ""

cleanup() {
    echo ""
    step "Shutting down frontend"
    kill $FRONTEND_PID 2>/dev/null || true
    ok "Frontend stopped"
    echo -e "  Containers still running. Run ${YELLOW}./scripts/stop.sh${NC} to stop everything."
    echo ""
}
trap cleanup EXIT INT TERM

wait $FRONTEND_PID
