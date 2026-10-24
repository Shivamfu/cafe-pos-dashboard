"""
Main FastAPI Application for Velvet Roast Cafe POS Backend.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
import os
from contextlib import asynccontextmanager

from app.config import settings
from app.database import init_db
from app.routers import tables, menu, orders, checkout, kds, inventory, shift, websocket, analytics

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database and seed initial floor plan & menu
    init_db()
    yield

app = FastAPI(
    title="Velvet Roast Cafe POS API",
    description="Backend API for Cafe POS Floor Plan Table Dashboard, Billing, KDS, and Inventory (Stitch Project: 3304540266501701245)",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(tables.router)
app.include_router(menu.router)
app.include_router(orders.router)
app.include_router(checkout.router)
app.include_router(kds.router)
app.include_router(inventory.router)
app.include_router(shift.router)
app.include_router(analytics.router)
app.include_router(websocket.router)

# Mount Static frontend files
static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "cafe_name": settings.CAFE_NAME,
        "terminal_id": settings.TERMINAL_ID,
        "database": "sqlite_wal_active"
    }

@app.get("/", tags=["Dashboard UI"])
async def root_dashboard():
    dashboard_path = os.path.join(static_dir, "index.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    return HTMLResponse("<h1>Velvet Roast Cafe POS API</h1><p>Visit <a href='/docs'>/docs</a> for interactive Swagger API documentation.</p>")
