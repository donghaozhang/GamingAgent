#!/usr/bin/env python
"""
Qwen Image URL Test

This script tests Qwen VL with a public image URL.
"""

import os
import sys
import argparse
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("Error: OPENROUTER_API_KEY not found in environment")
    sys.exit(1)

# Qwen model
QWEN_MODEL = "qwen/qwen2.5-vl-72b-instruct:free"

# Test with a public image
DEFAULT_IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/Tetris-logo.svg/1920px-Tetris-logo.svg.png"

def main():
    parser = argparse.ArgumentParser(description="Test Qwen VL with image URL")
    parser.add_argument("--url", default=DEFAULT_IMAGE_URL, help="URL of image to analyze")
    args = parser.parse_args()
    
    print(f"Using image URL: {args.url}")
    
    # Create client
    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1"
    )
    
    # Create message with URL following the OpenAI format instead
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": args.url
                    }
                },
                {"type": "text", "text": "What is shown in this image? Please describe it in detail."}
            ]
        }
    ]
    
    try:
        print("Sending request to Qwen...")
        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://github.com/lmgame-org/GamingAgent", 
                "X-Title": "Qwen VL URL Test"
            },
            model=QWEN_MODEL,
            messages=messages,
            max_tokens=1000
        )
        
        print("\n" + "="*60)
        print("Qwen Response:")
        print(response.choices[0].message.content)
        print("="*60)
    
    except Exception as e:
        print(f"Error calling API: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 