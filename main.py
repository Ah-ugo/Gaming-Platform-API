from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from api.routes import auth, users, games, deposits, stats, transactions
from db.database import connect_to_mongo, close_mongo_connection

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Gaming Platform API",
    version="1.0.0",
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Events
@app.on_event("startup")
async def startup_db_client():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_db_client():
    await close_mongo_connection()

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(games.router, prefix="/api/games", tags=["Games"])
app.include_router(deposits.router, prefix="/api/deposits", tags=["Deposits"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["Transactions"])
app.include_router(stats.router, prefix="/api/stats", tags=["Statistics"])

@app.get("/api/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}


