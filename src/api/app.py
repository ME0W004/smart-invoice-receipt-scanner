from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.settings import get_settings
from src.core.logger import app_logger
from src.api.routes import router as api_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern lifespan handler managing startup and graceful shutdown."""
    settings.ensure_directories()
    app_logger.info("Smart Invoice & Receipt Scanner API initialized and ready.")
    yield
    app_logger.info("Shutting down Smart Invoice & Receipt Scanner API.")


app = FastAPI(
    title="Smart Invoice & Receipt Scanner API",
    description="Industrial financial document extraction using IBM Docling, Instructor, and Paperless-ngx patterns.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Enable CORS for internal enterprise dashboards or n8n frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
