from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.state import health_status
from api.routes import router
from app.core.db import init_db_pool, close_db_pool
from app.core.redis_client import check_redis_health,redis_client
import asyncio
from services.proxy_engine import monitor_provider_health


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Botting up the Gateway infrastructure")
    await init_db_pool()
    await check_redis_health()
    asyncio.create_task(monitor_provider_health())
    print("💓 Active Health Monitor Started")
    
    yield

    print("Shutting down the Gateway infrastructure")
    await close_db_pool()
    await redis_client.redis_pool.close()
app = FastAPI(
    title="Tandem AI Gateway Proxy", 
    description="High-throughput LLM routing with Redis state management.",
    lifespan=lifespan
)

# Attach your endpoint routes
app.include_router(router)
