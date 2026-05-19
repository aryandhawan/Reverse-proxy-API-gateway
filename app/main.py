from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.state import health_status
from api.routes import router
from app.core.db import init_db_pool, close_db_pool
from app.core.redis_client import check_redis_health

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Botting up the Gateway infrastructure")
    await init_db_pool()
    await check_redis_health()
    yield

    print("Shutting down the Gateway infrastructure")
    await close_db_pool()

app = FastAPI(
    title="Tandem AI Gateway Proxy", 
    description="High-throughput LLM routing with Redis state management.",
    lifespan=lifespan
)

# Attach your endpoint routes
app.include_router(router)
