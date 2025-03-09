#!/usr/bin/env python
"""
Qwen Image Description

This script uses Qwen VL Max to describe an image.

Usage:
    python qwen_image_describe.py --image <path_to_image> [--url <image_url>]
    
    If --url is provided, it will use the URL instead of a local image.

Requirements:
    - openai
    - python-dotenv
    - Pillow (PIL)
"""

import os
import sys
import base64
import argparse
from io import BytesIO
from dotenv import load_dotenv
from PIL import Image
from openai import OpenAI

# Load API key from environment
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("Error: OPENROUTER_API_KEY environment variable not found.")
    print("Please create a .env file with your API key or set it in your environment.")
    sys.exit(1)

# Qwen model - using the one from the example
QWEN_MODEL = "qwen/qwen-vl-max"

def encode_image(image_path):
    """
    Encode an image from a file path
    
    Args:
        image_path (str): Path to the image file
    
    Returns:
        str: Base64-encoded image data URL
    """
    try:
        print(f"Opening image: {image_path}")
        # Open the image
        img = Image.open(image_path)
        print(f"Image opened. Mode: {img.mode}, Size: {img.size}")
        
        # Convert RGBA to RGB if needed
        if img.mode == 'RGBA':
            print("Converting RGBA image to RGB")
            img = img.convert('RGB')
        
        # Convert to bytes
        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=95)
        buffered.seek(0)
        
        # Get base64 encoded image
        img_bytes = buffered.getvalue()
        base64_image = base64.b64encode(img_bytes).decode("utf-8")
        print(f"Successfully encoded image, size: {len(base64_image)} bytes")
        
        # Return as data URL
        return f"data:image/jpeg;base64,{base64_image}"
    except Exception as e:
        print(f"Error encoding image: {e}")
        import traceback
        traceback.print_exc()
        return None

def describe_image_with_url(image_url, question="What is in this image?"):
    """
    Send image URL to Qwen VL model and get description
    
    Args:
        image_url (str): URL of the image
        question (str): Question about the image
    
    Returns:
        str: Model's description of the image
    """
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
        
        print(f"Using image URL: {image_url}")
        print(f"Sending request to model: {QWEN_MODEL}")
        
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://github.com/lmgame-org/GamingAgent",
                "X-Title": "Qwen VL Image Describer",
            },
            model=QWEN_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": question
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
        
        return completion.choices[0].message.content
    
    except Exception as e:
        print(f"Error calling API: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}"

def describe_image(image_path, question="What is in this image?"):
    """
    Send local image to Qwen VL model and get description
    
    Args:
        image_path (str): Path to the image file
        question (str): Question about the image
    
    Returns:
        str: Model's description of the image
    """
    # For local images, we'll encode and use the data URL approach
    encoded_image = encode_image(image_path)
    if not encoded_image:
        return "Failed to encode image"
    
    # Use the URL-based function with our data URL
    return describe_image_with_url(encoded_image, question)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Qwen VL Image Description")
    parser.add_argument("--image", type=str, help="Path to the image file")
    parser.add_argument("--url", type=str, help="URL of the image to analyze (instead of local file)")
    parser.add_argument("--prompt", type=str, default="What is in this image?", 
                      help="Question or prompt about the image")
    
    args = parser.parse_args()
    
    # Check that either image or URL is provided
    if not args.image and not args.url:
        print("Error: You must provide either --image or --url")
        parser.print_help()
        sys.exit(1)
    
    # If local image path is provided, check if it exists
    if args.image and not os.path.isfile(args.image):
        print(f"Error: Image file not found: {args.image}")
        sys.exit(1)
    
    print(f"Prompt: {args.prompt}")
    
    # Get description from Qwen
    if args.url:
        # Use image URL directly
        description = describe_image_with_url(args.url, args.prompt)
    else:
        # Use local image file
        description = describe_image(args.image, args.prompt)
    
    # Print response
    print("\n" + "="*60)
    print("Qwen VL Description:")
    print(description)
    print("="*60)

if __name__ == "__main__":
    main() 