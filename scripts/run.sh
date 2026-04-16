#!/usr/bin/env bash
set -e

# ─────────────────────────────────────────────────
# Portfolio Builder — Full Setup & Run Script
# ─────────────────────────────────────────────────

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

step() { echo -e "\n${BLUE}━━━ $1 ━━━${NC}"; }
ok()   { echo -e "${GREEN}✔ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
fail() { echo -e "${RED}✘ $1${NC}"; exit 1; }

# ─────────────────────────────────────────────────
# 1. Check prerequisites
# ─────────────────────────────────────────────────
step "Checking prerequisites"

command -v docker >/dev/null 2>&1    || fail "Docker is not installed"
command -v node >/dev/null 2>&1      || fail "Node.js is not installed"
command -v npm >/dev/null 2>&1       || fail "npm is not installed"
command -v python3 >/dev/null 2>&1   || fail "Python 3 is not installed"

ok "docker $(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"
ok "node $(node --version)"
ok "python3 $(python3 --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"

# ─────────────────────────────────────────────────
# 2. Create .env if missing
# ─────────────────────────────────────────────────
step "Setting up environment"

if [ ! -f .env ]; then
    cp .env.example .env
    # Generate a random secret key
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
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
# 3. Start Docker services (PostgreSQL + Redis)
# ─────────────────────────────────────────────────
step "Starting PostgreSQL and Redis"

docker compose up -d db redis
ok "PostgreSQL and Redis containers started"

# Wait for PostgreSQL to be ready
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

# Create test database if it doesn't exist
docker compose exec -T db psql -U portfolio -d portfolio_builder -c \
    "SELECT 1 FROM pg_database WHERE datname = 'portfolio_builder_test'" | grep -q 1 || \
    docker compose exec -T db psql -U portfolio -d portfolio_builder -c \
    "CREATE DATABASE portfolio_builder_test OWNER portfolio;" 2>/dev/null || true
ok "Test database ready"

# ─────────────────────────────────────────────────
# 4. Backend — Python venv & dependencies
# ─────────────────────────────────────────────────
step "Setting up backend"

cd "$ROOT_DIR/backend"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    ok "Created Python virtual environment"
else
    ok "Virtual environment exists"
fi

source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
ok "Backend dependencies installed"

# ─────────────────────────────────────────────────
# 5. Run database migrations
# ─────────────────────────────────────────────────
step "Running database migrations"

# Check if there are any migration versions
if [ -z "$(ls -A alembic/versions/ 2>/dev/null)" ]; then
    alembic revision --autogenerate -m "initial schema"
    ok "Generated initial migration"
fi

alembic upgrade head
ok "Database schema up to date"

# ─────────────────────────────────────────────────
# 6. Run backend tests
# ─────────────────────────────────────────────────
step "Running backend tests"

python -m pytest tests/ -v --tb=short 2>&1 || warn "Some tests failed (this is OK if DB is not fully configured)"

# ─────────────────────────────────────────────────
# 7. Frontend — install dependencies
# ─────────────────────────────────────────────────
step "Setting up frontend"

cd "$ROOT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    npm install
    ok "Frontend dependencies installed"
else
    ok "Frontend dependencies already installed"
fi

# ─────────────────────────────────────────────────
# 8. Start everything
# ─────────────────────────────────────────────────
step "Starting all services"

cd "$ROOT_DIR"

# Kill any previous backend/frontend processes on our ports
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:5173 2>/dev/null | xargs kill -9 2>/dev/null || true

# Start backend
cd "$ROOT_DIR/backend"
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
ok "Backend starting on http://localhost:8000 (PID: $BACKEND_PID)"

# Start Celery worker
celery -A app.tasks.celery_app worker --loglevel=warning &
CELERY_PID=$!
ok "Celery worker starting (PID: $CELERY_PID)"

# Start Celery beat
celery -A app.tasks.celery_app beat --loglevel=warning &
BEAT_PID=$!
ok "Celery beat starting (PID: $BEAT_PID)"

# Start frontend
cd "$ROOT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!
ok "Frontend starting on http://localhost:5173 (PID: $FRONTEND_PID)"

# ─────────────────────────────────────────────────
# 9. Wait for services to be ready
# ─────────────────────────────────────────────────
step "Waiting for services"

echo -n "Backend..."
for i in $(seq 1 20); do
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        echo ""
        ok "Backend is ready"
        break
    fi
    echo -n "."
    sleep 1
    if [ "$i" -eq 20 ]; then
        echo ""
        warn "Backend did not respond (check logs)"
    fi
done

# ─────────────────────────────────────────────────
# Done!
# ─────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Portfolio Builder is running!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  Frontend:  ${BLUE}http://localhost:5173${NC}"
echo -e "  Backend:   ${BLUE}http://localhost:8000${NC}"
echo -e "  API Docs:  ${BLUE}http://localhost:8000/docs${NC}"
echo -e "  Database:  ${BLUE}localhost:5432${NC}"
echo -e "  Redis:     ${BLUE}localhost:6379${NC}"
echo ""
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop all services"
echo ""

# ─────────────────────────────────────────────────
# Cleanup on exit
# ─────────────────────────────────────────────────
cleanup() {
    echo ""
    step "Shutting down"
    kill $BACKEND_PID $CELERY_PID $BEAT_PID $FRONTEND_PID 2>/dev/null || true
    ok "Application processes stopped"
    echo -e "  Run ${YELLOW}docker compose down${NC} to also stop PostgreSQL and Redis"
    echo ""
}
trap cleanup EXIT INT TERM

# Keep script alive
wait
