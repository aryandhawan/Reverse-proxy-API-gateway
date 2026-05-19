# pydantic structures
import json
from pydantic import BaseModel,Field
from typing import Dict

class Message(BaseModel):
    role: str=Field(...,description="The role of the message sender, e.g., 'user', 'assistant', 'system'.")
    content: str=Field(...,description="The actual content of the message.")

class RequestBody(BaseModel):
    model: str=Field(...,description="The identifier of the model to use for inference.")
    messages: list[Message]=Field(...,description="A list of messages, where each message is a Message object containing the role and content.")
    max_tokens: int=Field(100,description="The maximum number of tokens to generate in the response.")
    temprature: float=Field(default=0.7,ge=0.0,le=2.0,description="The sampling temperature to use for generation. Higher values mean more random output.")

