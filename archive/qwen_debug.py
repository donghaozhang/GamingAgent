#!/usr/bin/env python
"""
Qwen VL Debug

This script thoroughly tests the Qwen VL API with OpenRouter,
providing detailed logs and error handling to diagnose issues.
"""

import os
import json
import sys
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("Error: OPENROUTER_API_KEY not found in .env file")
    sys.exit(1)

# Available Qwen VL models
MODELS = [
    "qwen/qwen2.5-vl-72b-instruct",     # Free tier
    "qwen/qwen2.5-vl-72b-instruct:free", # Explicitly free tier
    "qwen/qwen-vl-max",                  # Different model
    "anthropic/claude-3-sonnet-20240229" # Alternative VL model for comparison
]

# Test image
TEST_IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"

def print_separator():
    """Print a separator line"""
    print("\n" + "="*80 + "\n")

def test_model(model_id, image_url=TEST_IMAGE_URL):
    """
    Test a specific model with the provided image URL
    
    Args:
        model_id (str): OpenRouter model ID to test
        image_url (str): URL of the image to analyze
    """
    print_separator()
    print(f"Testing model: {model_id}")
    print(f"Using image: {image_url}")
    
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
                "X-Title": "Qwen VL Debug Test",
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
                                "url": image_url
                            }
                        }
                    ]
                }
            ]
        )
        
        # Print raw response for debugging
        print("\nRaw API response:")
        try:
            print(f"Response type: {type(response)}")
            print(f"Response dir: {dir(response)}")
            print(f"Response model: {response.model}")
            
            if hasattr(response, 'choices') and response.choices:
                print(f"Number of choices: {len(response.choices)}")
                if len(response.choices) > 0:
                    choice = response.choices[0]
                    print(f"First choice type: {type(choice)}")
                    print(f"First choice dir: {dir(choice)}")
                    if hasattr(choice, 'message') and choice.message:
                        print(f"Message content: {choice.message.content}")
                    else:
                        print("Message is None or doesn't have content")
                else:
                    print("No choices in response")
            else:
                print("No choices attribute or it's empty")
                
            # Try to access the content safely
            content = None
            try:
                if response.choices and response.choices[0].message:
                    content = response.choices[0].message.content
            except Exception as e:
                print(f"Error accessing content: {e}")
                
            if content:
                print("\nModel Response:")
                print(content)
            else:
                print("\nNo content found in response")
                
        except Exception as e:
            print(f"Error processing response: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"API call error: {e}")
        import traceback
        traceback.print_exc()
        
def test_alternative_format(model_id):
    """
    Test an alternative format for the API call
    
    Args:
        model_id (str): OpenRouter model ID to test
    """
    print_separator()
    print(f"Testing alternative format with model: {model_id}")
    
    # Initialize client
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
    
    try:
        # Make API call with alternative format
        print("Making API call with alternative format...")
        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://github.com/lmgame-org/GamingAgent", 
                "X-Title": "Qwen VL Debug Test",
            },
            model=model_id,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful vision model that can see and describe images."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Look at this image and describe what you see in detail."},
                        {
                            "type": "image_url",
                            "image_url": {"url": TEST_IMAGE_URL}
                        }
                    ]
                }
            ],
            temperature=0.2,
            max_tokens=300
        )
        
        # Try to access the content safely
        try:
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                print("\nModel Response:")
                print(content)
            else:
                print("\nNo valid response received")
        except Exception as e:
            print(f"Error accessing content: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"API call error: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function"""
    print("Qwen VL API Debug Test")
    print(f"API Key: {OPENROUTER_API_KEY[:4]}...{OPENROUTER_API_KEY[-4:]}")
    
    # Test each model
    for model in MODELS:
        test_model(model)
    
    # Test alternative format with the first model
    test_alternative_format(MODELS[0])
    
    print_separator()
    print("Debug tests completed")

if __name__ == "__main__":
    main() 