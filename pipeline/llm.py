import os
from pathlib import Path
import anthropic
import yaml
from dotenv import load_dotenv
import base64
import io
from PIL import Image

load_dotenv()

MODEL = "claude-haiku-5-5"
PRICES_PATH = Path(__file__).resolve().parent.parent / "config" / "prices.yaml"

with open(PRICES_PATH, encoding = "utf_8") as f:
    PRICES = yaml.safe_load(f)

client = anthropic.Anthropic(api_key = os.environ.get("ANTHROPIC_API_KEY")) 

def image_block(image_path, longest_side = 768): #used to prepare an image for sending to Claude
    image = Image.open(image_path).convert("RGB")
    image.thumbnail((longest_side, longest_side))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    data = base64.b64encode(buffer.getvalue()).decode("ascii")
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}

def call_llm(system_prompt, user_prompt, max_tokens = 2000, image_path = None): #sends a prompt to Claude and returns the response, along with token usage and cost
    content = user_prompt
    if image_path is not None:
        content = [image_block(image_path), {"type": "text", "text": user_prompt}]
    response = client.messages.create(
        model = MODEL,
        max_tokens = max_tokens,
        system = system_prompt,
        messages = [
            {"role": "user", "content": content}
        ]
    )

    text = "".join(block.text for block in response.content if block.type == "text")

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    price = PRICES["llm"][MODEL]
    cost = (input_tokens * price["input_per_million"] + output_tokens * price["output_per_million"]) / 1000000

    return {
        "text" : text,
        "input_tokens" : input_tokens,
        "output_tokens" : output_tokens,
        "cost" : cost,
    } 