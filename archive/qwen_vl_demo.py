#!/usr/bin/env python
"""
Qwen2.5 VL 72B Instruct Demo

This script demonstrates how to use the Qwen2.5 VL 72B Instruct model via OpenRouter.
It can:
1. Process images from a file or URL
2. Ask questions about the images
3. Save the responses

Usage:
    python qwen_vl_demo.py --image <path_or_url> --question "What is in this image?"

Requirements:
    - openai
    - python-dotenv
    - requests
    - Pillow (PIL)
"""

import os
import sys
import base64
import argparse
import requests
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# Get API key from environment variables
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("Error: OPENROUTER_API_KEY environment variable not found.")
    print("Please create a .env file with your API key.")
    print("Example: OPENROUTER_API_KEY=your_api_key_here")
    sys.exit(1)

# Model ID for Qwen2.5 VL 72B Instruct
MODEL_QWEN_VL = "qwen/qwen2.5-vl-72b-instruct:free"

class QwenVLClient:
    """Client for interacting with Qwen2.5 VL 72B Instruct model via OpenRouter"""
    
    def __init__(self, api_key=None, model=MODEL_QWEN_VL):
        """
        Initialize the Qwen VL client
        
        Args:
            api_key (str): OpenRouter API key. If None, uses environment variable
            model (str): Model ID to use
        """
        self.api_key = api_key or OPENROUTER_API_KEY
        self.model = model
        
        # Initialize OpenAI client with OpenRouter base URL
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        
        print(f"Initialized QwenVLClient with model: {self.model}")
    
    def encode_image(self, image_path_or_url):
        """
        Encode an image as base64 from a file path or URL
        
        Args:
            image_path_or_url (str): Path to image file or URL
            
        Returns:
            str: Base64-encoded image or URL
        """
        # Check if it's a URL
        if image_path_or_url.startswith(('http://', 'https://')):
            print(f"Using image URL: {image_path_or_url}")
            return image_path_or_url
        
        # Otherwise, load from file and encode
        try:
            with open(image_path_or_url, "rb") as image_file:
                image_data = image_file.read()
                base64_image = base64.b64encode(image_data).decode("utf-8")
                print(f"Encoded image from file: {image_path_or_url}")
                return f"data:image/jpeg;base64,{base64_image}"
        except Exception as e:
            print(f"Error encoding image: {e}")
            sys.exit(1)
    
    def analyze_image(self, image_path_or_url, question="What is in this image?"):
        """
        Analyze an image using Qwen2.5 VL model
        
        Args:
            image_path_or_url (str): Path to image file or URL
            question (str): Question to ask about the image
            
        Returns:
            str: Model's response
        """
        print(f"Analyzing image with question: '{question}'")
        
        # Prepare the image
        image_data = self.encode_image(image_path_or_url)
        
        # Determine if we're using a URL or base64 data
        if image_data.startswith(('http://', 'https://')):
            image_content = {
                "type": "image_url",
                "image_url": {
                    "url": image_data
                }
            }
        else:
            image_content = {
                "type": "image_url",
                "image_url": {
                    "url": image_data
                }
            }
        
        try:
            # Call the API
            response = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://github.com/lmgame-org/GamingAgent",
                    "X-Title": "Qwen VL Demo"
                },
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": question
                            },
                            image_content
                        ]
                    }
                ]
            )
            
            # Extract and return the response
            if hasattr(response, 'choices') and len(response.choices) > 0:
                return response.choices[0].message.content
            return "No valid response received"
            
        except Exception as e:
            print(f"Error calling API: {e}")
            return f"Error: {str(e)}"

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Qwen2.5 VL 72B Instruct Demo")
    parser.add_argument("--image", type=str, required=True, help="Path to image file or URL")
    parser.add_argument("--question", type=str, default="What is in this image?", 
                        help="Question to ask about the image")
    parser.add_argument("--save", type=str, help="Save response to file")
    
    args = parser.parse_args()
    
    # Initialize client
    client = QwenVLClient()
    
    # Analyze image
    response = client.analyze_image(args.image, args.question)
    
    # Print response
    print("\n" + "="*50)
    print("Qwen2.5 VL Response:")
    print(response)
    print("="*50 + "\n")
    
    # Save response if requested
    if args.save:
        try:
            with open(args.save, "w", encoding="utf-8") as f:
                f.write(f"Question: {args.question}\n\n")
                f.write(f"Response:\n{response}")
            print(f"Response saved to: {args.save}")
        except Exception as e:
            print(f"Error saving response: {e}")

if __name__ == "__main__":
    main() 