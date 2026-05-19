import os
from fastapi import HTTPException
from huggingface_hub import AsyncInferenceClient, InferenceClientError
from google import genai
from google.genai import types
from dotenv import load_dotenv
from app.core.redis_client import redis_pool
from schemas import RequestBody, Message
from app.core.state import health_status

load_dotenv()

# Instantiations
hf_client = AsyncInferenceClient(token=os.getenv("HF_TOKEN"))

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable not set")
gemini_client = genai.Client(api_key=api_key)

async def _execute_gemini_fallback(request_body: RequestBody):
    """private helper function to execute the gemini fallback logic"""
    gemini_contents = []
    for msg in request_body.messages:
        role = "model" if msg.role == "assistant" else msg.role
        gemini_contents.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg.content)]
            )
        )
    system_instruction = "You are a helpful assistant that provides concise answers to questions."
    
    fallback_response = await gemini_client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=gemini_contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=request_body.max_tokens,
            temperature=request_body.temperature
        )
    )
    return fallback_response.text
async def call_huggingface_proxy(request_body: RequestBody)->tuple[str,str]:
    circuit_key="circuit breaker: huggingface"
    # check if circuit is open for huggingface
    is_hf_down=await redis_pool.get(circuit_key)

    if is_hf_down:
        print("Huggingface is currently marked as down. Executing fallback.")
        health_status["huggingface"] = False
        fallback_text=await _execute_gemini_fallback(request_body)
        return fallback_text,"gemini"
    
    
    try:
        messages=[{"role": msg.role,  "content": msg.content} for msg in request_body.messages]
        response=await hf_client.chat.completions.create(
            model=request_body.model,
            messages=messages,
            max_tokens=request_body.max_tokens,
            temperature=request_body.temperature,
            timeout=5.0
        )

        return response.choices[0].message.content,"huggingface"
    
    except (InferenceClientError, Exception) as e:
        print(f"Huggingface proxy error: {str(e)} falling back to Gemini")
        health_status["huggingface"] = False
        # fallback to gemini
        gemini_contents = []
        for msg in request_body.messages:
            role = "model" if msg.role == "assistant" else msg.role
            gemini_contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg.content)]
                )
            )
        system_instruction = "You are a helpful assistant that provides concise answers to questions."
        
        fallback_response = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=gemini_contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=request_body.max_tokens,
                temperature=request_body.temperature
            )
        )

        return fallback_response.text,"gemini"