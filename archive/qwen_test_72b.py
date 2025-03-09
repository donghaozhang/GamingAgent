#!/usr/bin/env python
"""
Qwen 2.5 VL 72B Instruct - Direct Test

This script exactly replicates the user's example, using qwen/qwen2.5-vl-72b-instruct.
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("Error: OPENROUTER_API_KEY not found in .env file")
    exit(1)

print("Testing with model: qwen/qwen2.5-vl-72b-instruct")
print("Using image: https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg")

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=OPENROUTER_API_KEY,
)

try:
    completion = client.chat.completions.create(
      extra_headers={
        "HTTP-Referer": "https://github.com/lmgame-org/GamingAgent", 
        "X-Title": "Qwen VL Test",
      },
      model="qwen/qwen2.5-vl-72b-instruct",
      messages=[
        {
          "role": "user",
          "content": [
            {
              "type": "text",
              "text": "What is in this image?"
            },
            {
              "type": "image_url",
              "image_url": {
                "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
              }
            }
          ]
        }
      ]
    )
    print("\n" + "="*60)
    print("Response from Qwen 2.5 VL 72B:")
    print(completion.choices[0].message.content)
    print("="*60)
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc() 