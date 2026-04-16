from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.api.portfolios import router as portfolios_router
from app.api.profiles import router as profiles_router
from app.database import SessionLocal
from app.data.seed import seed_country_restrictions

app = FastAPI(title="Portfolio Builder", version="0.1.0")


@app.on_event("startup")
def startup():
    db = SessionLocal()
    try:
        seed_country_restrictions(db)
    finally:
        db.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(profiles_router)
app.include_router(portfolios_router)


@app.get("/health")
def health():
    return {"status": "ok"}
