import os
import sys
import base64
from io import BytesIO
from PIL import Image
import time
import re

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from openai import OpenAI
import anthropic
import google.generativeai as genai
from model_providers.gemini_provider import GeminiProvider

# Optional import for OpenRouter (will be used if the key is available)
openrouter_client = None
try:
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        openrouter_client = OpenAI(
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/lmgame-org/GamingAgent"  # Site URL for OpenRouter
            }
        )
except ImportError:
    pass

def check_image(base64_image, provider_name):
    """Check if an image is empty or valid and print information about it."""
    if not base64_image:
        print(f"[{provider_name}] WARNING: Image is empty or None")
        return False
    
    # Check basic string properties
    img_len = len(base64_image)
    print(f"[{provider_name}] Base64 image string length: {img_len} characters")
    
    # Check if it's a valid base64 string (should be divisible by 4, contain only valid chars)
    if not re.match(r'^[A-Za-z0-9+/]+={0,2}$', base64_image):
        if ',' in base64_image:
            print(f"[{provider_name}] Image appears to have a data URL prefix (e.g., 'data:image/png;base64,')")
            # Extract just the base64 part after the comma
            base64_part = base64_image.split(',', 1)[1]
            print(f"[{provider_name}] Base64 part after prefix: {len(base64_part)} characters")
        else:
            print(f"[{provider_name}] Base64 string contains invalid characters")
    
    try:
        # Decode base64 image
        image_bytes = base64.b64decode(base64_image)
        img_bytes_len = len(image_bytes)
        print(f"[{provider_name}] Decoded image size: {img_bytes_len} bytes")
        
        img = Image.open(BytesIO(image_bytes))
        
        # Get image info
        width, height = img.size
        format = img.format
        mode = img.mode
        
        print(f"[{provider_name}] Image is valid: {width}x{height} pixels, Format: {format}, Mode: {mode}")
        
        # Check if image content is mostly empty (optional)
        if width * height > 0:
            # Convert to grayscale and get pixel data
            img_gray = img.convert('L')
            pixels = list(img_gray.getdata())
            avg_pixel = sum(pixels) / len(pixels)
            print(f"[{provider_name}] Average pixel value: {avg_pixel:.2f}/255 (higher is brighter)")
            
            # Save a debug copy of the image
            debug_dir = os.path.join("debug_images")
            os.makedirs(debug_dir, exist_ok=True)
            debug_path = os.path.join(debug_dir, f"{provider_name}_debug_{int(time.time())}.png")
            img.save(debug_path)
            print(f"[{provider_name}] Saved debug image to: {debug_path}")
        
        return True
    except Exception as e:
        print(f"[{provider_name}] ERROR checking image: {e}")
        return False

def openai_completion(system_prompt, model_name, base64_image, prompt):
    # Check if image is valid
    image_valid = check_image(base64_image, "OpenAI")
    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt
                    },
                ],
            }
        ]

    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=0,
        max_tokens=1024,
    )

    generated_code_str = response.choices[0].message.content
     
    return generated_code_str

def anthropic_completion(system_prompt, model_name, base64_image, prompt):
    # Check if image is valid
    image_valid = check_image(base64_image, "Anthropic")
    
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    # Create the message content with proper formatting for Claude
    content = []
    
    # Add image if it's valid
    if image_valid and base64_image:
        # Make sure the image data doesn't contain any prefixes (like data:image/png;base64,)
        # Claude expects just the raw base64 data
        if "," in base64_image:
            # If there's a prefix, remove it
            base64_image = base64_image.split(",", 1)[1]
        
        # Add the image to the content array
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64_image,
            },
        })
    else:
        print("[Anthropic] No valid image to send to Claude")
    
    # Add the text prompt
    content.append({
        "type": "text",
        "text": prompt
    })
    
    # Create the final message structure
    messages = [
        {
            "role": "user",
            "content": content
        }
    ]

    print(f"[Anthropic] Sending message with {len(content)} content parts to Claude")
    
    with client.messages.stream(
            max_tokens=1024,
            messages=messages,
            temperature=0,
            system=system_prompt,
            model=model_name, # claude-3-5-sonnet-20241022 # claude-3-7-sonnet-20250219
        ) as stream:
            partial_chunks = []
            for chunk in stream.text_stream:
                partial_chunks.append(chunk)
        
    generated_code_str = "".join(partial_chunks)
    
    return generated_code_str

def gemini_completion(system_prompt, model_name, base64_image, prompt):
    # Check if image is valid
    image_valid = check_image(base64_image, "Gemini")
    
    # Create or get the provider (could be cached for performance)
    provider = GeminiProvider(model=model_name)
    
    # Get completion directly from the provider
    generated_code_str = provider.get_completion(
        system_prompt=system_prompt,
        prompt=prompt,
        base64_image=base64_image
    )
    
    return generated_code_str

def openrouter_completion(system_prompt, model_name, base64_image, prompt):
    """
    Get a completion from Claude 3.7 Sonnet via OpenRouter API.
    
    Args:
        system_prompt (str): The system prompt for the model.
        model_name (str): The model name to use (e.g., "anthropic/claude-3-7-sonnet:thinking").
        base64_image (str, optional): Base64-encoded image data.
        prompt (str): The text prompt to send to the model.
        
    Returns:
        str: The model's response text.
    """
    # Check if image is valid
    image_valid = check_image(base64_image, "OpenRouter")
    
    # Declare global client variable
    global openrouter_client
    
    # Verify OpenRouter client is available
    if not openrouter_client:
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if not openrouter_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set. Please check your .env file.")
        
        openrouter_client = OpenAI(
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/lmgame-org/GamingAgent"  # Site URL for OpenRouter
            }
        )
    
    # Create content array to hold message components
    user_message = {}
    
    # Check if this is a Claude model (requires different formatting)
    if "anthropic/claude" in model_name:
        # Claude format with content array
        content = []
        
        # Add image if it's valid
        if image_valid and base64_image:
            # Make sure the image data doesn't contain any prefixes (like data:image/png;base64,)
            # Claude expects just the raw base64 data
            if "," in base64_image:
                # If there's a prefix, remove it
                base64_image = base64_image.split(",", 1)[1]
            
            # Add the image to the content array
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64_image,
                },
            })
        else:
            print("[OpenRouter] No valid image to send to Claude")
        
        # Add the text prompt
        content.append({
            "type": "text",
            "text": prompt
        })
        
        # Set the user message
        user_message = {
            "role": "user",
            "content": content
        }
        
        print(f"[OpenRouter] Sending message with {len(content)} content parts to Claude via OpenRouter")
    else:
        # Standard OpenAI format for non-Claude models
        message_content = []
        
        # Add text content
        message_content.append({
            "type": "text", 
            "text": prompt
        })
        
        # Add image if provided and valid
        if image_valid and base64_image:
            # Add full data URL if not present
            if not base64_image.startswith("data:"):
                base64_image = f"data:image/png;base64,{base64_image}"
                
            message_content.append({
                "type": "image_url",
                "image_url": {
                    "url": base64_image
                }
            })
            
        # Set the user message
        user_message = {
            "role": "user",
            "content": message_content
        }
    
    try:
        # Call the OpenRouter API
        response = openrouter_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                user_message
            ],
            max_tokens=2048,
            temperature=0.2
        )
        
        # Extract text from the response
        if hasattr(response, 'choices') and len(response.choices) > 0:
            return response.choices[0].message.content
        return "No valid response from OpenRouter"
    
    except Exception as e:
        print(f"[OpenRouter] Error: {e}")
        # Return a fallback response
        return "I'll use pygame.K_DOWN to move the piece down faster."  # Fallback response