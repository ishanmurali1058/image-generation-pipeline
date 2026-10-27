import io
import urllib.request
import fal_client
from PIL import Image

from pipeline.llm import PRICES

IMAGE_MODEL = "fal-ai/flux/schnell"

def generate_image(prompt, png_path, width=1024, height=768):
    result = fal_client.subscribe(IMAGE_MODEL, arguments={
        "prompt": prompt,
        "image_size": {"width": width, "height": height},
        "num_images": 1,
        "enable_safety_checker": True,
    })

    with urllib.request.urlopen(result["images"][0]["url"]) as response:
        data = response.read()
    Image.open(io.BytesIO(data)).convert("RGB").save(png_path)

    megapixels = width * height / 1_000_000
    cost = megapixels * PRICES["image"][IMAGE_MODEL]["per_megapixel"]
    flagged = bool((result.get("has_nsfw_concepts") or [False])[0])
    return {"cost": cost, "safety_flagged": flagged}