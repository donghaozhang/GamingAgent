#!/usr/bin/env python
"""
Vision Model Success Demo

This script demonstrates successful vision capabilities with OpenRouter
using Claude 3 Sonnet instead of Qwen models.
"""

import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("Error: OPENROUTER_API_KEY not found in .env file")
    sys.exit(1)

# Test image
TEST_IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"

def print_separator():
    """Print a separator line"""
    print("\n" + "="*80 + "\n")

def test_claude_vision():
    """Test Claude 3 Sonnet vision capabilities"""
    model_id = "anthropic/claude-3-sonnet-20240229"
    
    print_separator()
    print(f"Testing model: {model_id}")
    print(f"Using image: {TEST_IMAGE_URL}")
    
    # Initialize client
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
    
    try:
        # Make API call
        print("Making API call...")
        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://github.com/lmgame-org/GamingAgent", 
                "X-Title": "Vision Model Test",
            },
            model=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "What is in this image? Describe it in detail."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": TEST_IMAGE_URL
                            }
                        }
                    ]
                }
            ]
        )
        
        # Access the content
        content = response.choices[0].message.content
        print("\nModel Response:")
        print(content)
                
    except Exception as e:
        print(f"API call error: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function"""
    print("Vision Model Success Demo")
    print(f"API Key: {OPENROUTER_API_KEY[:4]}...{OPENROUTER_API_KEY[-4:]}")
    
    # Test Claude 3 vision
    test_claude_vision()
    
    print_separator()
    print("Test completed")

if __name__ == "__main__":
    main() 