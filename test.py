from __future__ import annotations

import os

from openai import OpenAI


api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is required.")

client = OpenAI(api_key=api_key)

res = client.chat.completions.create(
    model=os.environ.get("OPENAI_MODEL", "gpt-5.4-mini"),
    messages=[{"role": "user", "content": "hi"}],
)

print(res)
