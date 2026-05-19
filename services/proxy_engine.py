import asyncio
import os
from openai import AsyncOpenAI
from google import genai
from google.genai import types
from dotenv import load_dotenv
from app.core import redis_client
from api.schemas import RequestBody

load_dotenv()

# Instantiations
primary_client = AsyncOpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable not set")
gemini_client = genai.Client(api_key=api_key)

async def monitor_provider_health():
    """Runs continuously in the background, checking provider heartbeats."""
    while True:
        try:
           
            await asyncio.wait_for(
                primary_client.chat.completions.create(
                    model="llama-3.1-8b-instant", 
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1
                ),
                timeout=2.0 
            )
            
          
            await redis_client.redis_pool.set("health:groq", "UP")
            
        except Exception:
           
            await redis_client.redis_pool.setex("health:groq", 60, "DOWN")
            print("💔 Groq Heartbeat: DOWN. Circuit proactively tripped.")

        # Sleep for 30 seconds before pinging again
        await asyncio.sleep(30)
async def _execute_gemini_fallback(request_body: RequestBody) -> str:
    """Bulletproof fallback using pure strings to prevent SDK typing errors."""
    try:
        user_prompt = request_body.messages[-1].content
        system_instruction = "You are a helpful assistant that provides concise answers to questions."
        
        fallback_response = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=request_body.max_tokens,
                temperature=request_body.temperature
            )
        )
        

        return fallback_response.text
        
    except Exception as e:
        print(f"🧨 FATAL: Gemini Fallback also failed: {e}")
        raise e


async def call_primary_proxy(request_body: RequestBody) -> tuple[str, str]:
    circuit_key = "circuit_breaker:primary"

    health_status=await redis_client.redis_pool.get("health:groq")
    
    is_down = await redis_client.redis_pool.get(circuit_key)
    if is_down:
        print("⚡ Circuit Breaker Open: Routing instantly to Gemini.")
        fallback_text = await _execute_gemini_fallback(request_body)
        return fallback_text, "gemini"

    try:
        if request_body.simulate_crash:
            raise Exception("Chaos Mode Activated: Intentional provider crash!")
        messages = [{"role": msg.role,  "content": msg.content} for msg in request_body.messages]
        response = await asyncio.wait_for(
            primary_client.chat.completions.create(
                model=request_body.model, 
                messages=messages,
                max_tokens=request_body.max_tokens,
                temperature=request_body.temperature
            ),
            timeout=5.0
        )
        return response.choices[0].message.content, "groq"

    except asyncio.TimeoutError:
        print("🚨 Primary proxy timeout. Tripping Circuit Breaker.")
        await redis_client.redis_pool.setex(circuit_key, 60, "down")
        fallback_text = await _execute_gemini_fallback(request_body)
        return fallback_text, "gemini"
        
    except Exception as e:
        print(f"🚨 Primary proxy error: {str(e)}. Tripping Circuit Breaker.")
        await redis_client.redis_pool.setex(circuit_key, 60, "down")
        fallback_text = await _execute_gemini_fallback(request_body)
        return fallback_text, "gemini"