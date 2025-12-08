import asyncio
from openai import AsyncClient
from pathlib import Path
import sys

# ensure repo root on path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rusty_2.common.settings import load_env, get_default_model_name, get_google_api_key


async def main_gemini():
    load_env()
    api_key = get_google_api_key()
    model = get_default_model_name()

    # Gemini OpenAI-compatible endpoint
    client = AsyncClient(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )

    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say hello in one short sentence."}],
    )
    print("LLM reply:", resp.choices[0].message.content)

async def main_openai():
    load_env()
    model = "gpt-4o-mini"

    client = AsyncClient()  # uses OPENAI_API_KEY from env by default

    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say hello in one short sentence."}],
    )
    print("LLM reply:", resp.choices[0].message.content)


if __name__ == "__main__":
    #asyncio.run(main_gemini())
    asyncio.run(main_openai())
