from fastapi import APIRouter, HTTPException,Response,Request,BackgroundTasks
import time 
from services.proxy_engine import call_primary_proxy 
from api.schemas import RequestBody,Message
from app.core import db
from app.core import redis_client
router = APIRouter()

@router.get("/health")
async def get_health_status():
    """Simple status check for your dashboard."""
    return {"status": "healthy for start"}

# background database writter

async def save_telemetry_log(primary_provider: str, routed_provider: str, latency_ms: float, status_code: int):
    """Saves telemetry data to the database asynchronously."""
    
    # Notice we use db.db_pool here to fetch the LIVE connection pool!
    if db.db_pool:
        try:
            async with db.db_pool.acquire() as connection:
                await connection.execute("""
                    INSERT INTO telemetry_logs (primary_provider, routed_provider, latency_ms, status_code)
                    VALUES ($1, $2, $3, $4);
                """, primary_provider, routed_provider, latency_ms, status_code)
        except Exception as e:
            # If PostgreSQL fails to write, print it so we aren't flying blind
            print(f"🚨 PostgreSQL Insert Error: {e}")
    else:
        print("⚠️ Warning: db.db_pool is None. Skipping telemetry insert.")
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

    request_count=await redis_client.redis_pool.incr(redis_key)

    if request_count == 1:
        await redis_client.redis_pool.expire(redis_key, 60)
        
   # rate limiter logic: max 5 requests per minute per IP address
    if request_count > 5:
        raise HTTPException(
            status_code=429, 
            detail="Rate limit exceeded. Maximum 5 requests per minute."
        )   
    
    start_time=time.perf_counter()
    status_code=200
    routed_provider="groq"
    try:
        
        llm_response_text, routed_provider = await call_primary_proxy(request_body)
        
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