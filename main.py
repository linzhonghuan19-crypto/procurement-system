import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from database import init_db, get_db, User
from auth import get_password_hash
from routes import auth, products, orders, ai, wecom

app = FastAPI(title="海外仓采购管理系统", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(ai.router)
app.include_router(wecom.router)


@app.on_event("startup")
def startup():
    init_db()
    # Create default admin user if not exists
    from database import SessionLocal
    db = SessionLocal()
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(
            username="admin",
            password_hash=get_password_hash("admin123"),
            display_name="管理员",
            role="admin",
        )
        db.add(admin)
        db.commit()
    db.close()


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api")
def api_root():
    return {
        "name": "海外仓采购管理系统 API",
        "version": "1.0.0",
        "endpoints": {
            "auth": "/api/auth",
            "products": "/api/products",
            "orders": "/api/orders",
            "ai": "/api/ai",
            "wecom": "/api/wecom",
        },
    }


# Serve the frontend SPA
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    # Only serve HTML for non-API routes
    if full_path.startswith("api/") or full_path.startswith("."):
        return {"error": "not found"}

    static_dir = Path(__file__).parent / "static"
    index_path = static_dir / "index.html"

    if not index_path.exists():
        return {"error": "frontend not built"}

    requested = static_dir / full_path
    if requested.exists() and requested.is_file():
        return FileResponse(str(requested))

    return FileResponse(str(index_path))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)