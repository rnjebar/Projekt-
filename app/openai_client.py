import os
from openai import OpenAI

client = OpenAI()

def generate_description(prompt: str, system_prompt: str, prompt_additions: str = "") -> str:
    # prompt_additions optional anhängen
    if prompt_additions:
        prompt = f"{prompt}\n\nZusatzinfos:\n{prompt_additions}"

    resp = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    )
    return resp.output_text