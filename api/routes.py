from fastapi import APIRouter, HTTPException,Response,Request,BackgroundTasks
from schemas import RequestBody
import time 
from services.proxy_engine import call_huggingface_proxy 
from api.schemas import RequestBody
from services.proxy_engine import execute_proxy_request
from app.core.db import init_db_pool,close_db_pool,db_pool
from app.core.redis_client import redis_pool,check_redis_health
router = APIRouter()

@router.get("/health")
async def get_health_status():
    """Simple status check for your dashboard."""
    return {"status": "healthy for start"}

# background database writter

async def save_telemetry_log(primary_provider: str,routed_provider: str,latency_ms: float,status_code: int):
    """Saves telemetry data to the database asynchronously."""
    if db_pool:
        async with db_pool.acquire() as connection:
            await connection.execute("""
                INSERT INTO telemetry_logs (primary_provider, routed_provider, latency_ms, status_code)
                VALUES ($1, $2, $3, $4);
            """, primary_provider, routed_provider, latency_ms, status_code)

@router.post("/v1/chat/completions")
async def proxy_inference(
    request: Request, 
    request_body: RequestBody, 
    response: Response, 
    background_tasks: BackgroundTasks
    ):
    """
    Receives the unified JSON schema and offloads the heavy 
    network lifting to the asynchronous proxy engine.
    """
    client_ip=request.client.host
    redis_key=f"rate limiter: {client_ip}"
    
    # increment the user's request count in Redis

    request_count=await redis_pool.incr(redis_key)

    if request_count>50:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    
    start_time=time.perf_counter()
    status_code=200
    routed_provider="huggingface"
    try:
        
        llm_response_text, routed_provider = await call_huggingface_proxy(request_body)
        
    except Exception as e:
        status_code = 500
        raise HTTPException(status_code=500, detail=f"Gateway Critical Failure: {str(e)}")
        
    finally:
        # Calculate Latency
        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        
        # Inject Telemetry Header
        response.headers["X-Gateway-Execution-Time-MS"] = str(execution_time_ms)

    # background task for database commit

    background_tasks.add_task(save_telemetry_log,primary_provider=request_body.model,routed_provider=routed_provider,latency_ms=execution_time_ms,status_code=status_code)

    return {
        "id": "chatcmpl-gateway-1",
        "object": "chat.completion",
        "choices": [{"message": {"role": "assistant", "content": llm_response_text}}],
        "gateway_telemetry": {"latency_ms": execution_time_ms, "status": status_code}
    }