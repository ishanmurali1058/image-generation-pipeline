import os
from pathlib import Path
import anthropic
import yaml
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-haiku-5-5"
PRICES_PATH = Path(__file__).resolve().parent.parent / "config" / "prices.yaml"

with open(PRICES_PATH, encoding = "utf_8") as f:
    PRICES = yaml.safe_load(f)

client = anthropic.Anthropic(api_key = os.environ.get("ANTHROPIC_API_KEY"))

def call_llm(system_prompt, user_prompt, max_tokens = 2000):
    response = client.messages.create(
        model = MODEL,
        max_tokens = max_tokens,
        system = system_prompt,
        messages = [
            {"role": "user", "content": user_prompt}
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