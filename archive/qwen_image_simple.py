#!/usr/bin/env python
"""
Qwen Image Simple Test

This is a minimal script to test sending images to Qwen VL using the exact format
from the documentation.
"""

import os
import sys
import base64
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

def encode_image_to_base64(image_path):
    """Encode image to base64"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def main():
    parser = argparse.ArgumentParser(description="Test Qwen VL with images")
    parser.add_argument("--image", required=True, help="Path to image file")
    args = parser.parse_args()
    
    # Check if image exists
    if not os.path.exists(args.image):
        print(f"Error: Image file not found: {args.image}")
        sys.exit(1)
    
    # Encode image
    try:
        base64_image = encode_image_to_base64(args.image)
        print(f"Successfully encoded image: {len(base64_image)} bytes")
    except Exception as e:
        print(f"Error encoding image: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Create client
    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1"
    )
    
    # Create message following the example format exactly
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": f"data:image;base64,{base64_image}"},
                {"type": "text", "text": "Describe this image."}
            ]
        }
    ]
    
    try:
        print("Sending request to Qwen...")
        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://github.com/lmgame-org/GamingAgent", 
                "X-Title": "Qwen VL Simple Test"
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