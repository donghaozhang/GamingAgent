#!/usr/bin/env python
"""
Gemini Pro Vision Direct Demo

This script demonstrates using Google's Gemini Pro Vision model
directly through Google's API rather than OpenRouter.
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("Error: GOOGLE_API_KEY not found in .env file")
    print("Please obtain an API key from: https://makersuite.google.com/app/apikey")
    sys.exit(1)

# Test image
TEST_IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"

def test_gemini_direct():
    """Test Gemini Pro Vision directly through Google's API"""
    print("\n" + "="*80 + "\n")
    print("Testing Gemini Pro Vision directly via Google's API")
    print(f"Using image: {TEST_IMAGE_URL}")
    
    # API endpoint
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent?key={GOOGLE_API_KEY}"
    
    # Request payload
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": "What is in this image? Describe it in detail."},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": "fetch_from_url",  # Special value to tell our code to fetch from URL
                        }
                    }
                ]
            }
        ],
        "generation_config": {
            "temperature": 0.4,
            "top_p": 1,
            "top_k": 32,
            "max_output_tokens": 2048,
        }
    }
    
    try:
        # Fetch image data
        print("Fetching image data...")
        image_response = requests.get(TEST_IMAGE_URL)
        if image_response.status_code != 200:
            raise Exception(f"Failed to fetch image: HTTP {image_response.status_code}")
        
        # Import base64 only when needed
        import base64
        
        # Convert image to base64
        image_base64 = base64.b64encode(image_response.content).decode('utf-8')
        
        # Update payload with base64 data
        payload["contents"][0]["parts"][1]["inline_data"]["data"] = image_base64
        
        # Make API call
        print("Making API call to Google...")
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers)
        
        # Check response
        if response.status_code != 200:
            print(f"API error: HTTP {response.status_code}")
            print(response.text)
            return
        
        # Process response
        response_json = response.json()
        if "candidates" in response_json and len(response_json["candidates"]) > 0:
            content = response_json["candidates"][0]["content"]
            if "parts" in content and len(content["parts"]) > 0:
                text = content["parts"][0]["text"]
                print("\nModel Response:")
                print(text)
            else:
                print("No parts found in response content")
        else:
            print("No candidates found in response")
            print(f"Full response: {response_json}")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Gemini Pro Vision Direct Demo")
    print(f"API Key: {GOOGLE_API_KEY[:4]}...{GOOGLE_API_KEY[-4:]}" if GOOGLE_API_KEY else "API Key: Not found")
    
    # Test Gemini vision directly
    test_gemini_direct()
    
    print("\n" + "="*80 + "\n")
    print("Test completed")
    print("NOTE: If you need a Google API key, visit: https://makersuite.google.com/app/apikey") 