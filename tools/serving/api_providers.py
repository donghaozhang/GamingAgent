import os
from dotenv import load_dotenv
import time
import base64
import json

# Load environment variables from .env file
load_dotenv()

from openai import OpenAI
import anthropic
import google.generativeai as genai

# Import extract_code function
from tools.utils import extract_code

# Avoid repeating import for extract_python_code
try:
    from tools.utils import extract_python_code
except ImportError:
    # If already imported, avoid repeating import error
    pass

def openai_completion(system_prompt, model_name, base64_image, prompt):
    """
    Call the OpenAI API with an image and prompt.
    
    Args:
        system_prompt: System prompt for the API
        model_name: OpenAI model name
        base64_image: Base64 encoded image
        prompt: User prompt
        
    Returns:
        str: Generated code from the API
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    messages = []
    
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    content = [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{base64_image}",
                "detail": "high"
            }
        },
        {
            "type": "text",
            "text": prompt
        }
    ]
    
    messages.append({"role": "user", "content": content})
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=4096,
        )
    except Exception as e:
        print(f"error: {e}")
        return "error", "error: " + str(e)
    
    full_response = response.choices[0].message.content
    generated_code_str = extract_code(full_response)
    
    return generated_code_str, full_response

def anthropic_completion(system_prompt, model_name, base64_image, prompt):
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": base64_image,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt
                        },
                    ],
                }
            ]
    
    t0 = time.time()
    
    print("Starting Anthropic API call...")
    system = None

    if system_prompt:
        system = system_prompt
    try:
        response = client.messages.create(
            model=model_name,
            max_tokens=4096,
            system=system,
            messages=messages
        )
    except Exception as e:
        print(f"error: {e}")
        return "error", "error: " + str(e)

    print("Anthropic API call completed successfully")
    
    t1 = time.time()

    full_response = response.content[0].text
    generated_code_str = extract_code(full_response)

    return generated_code_str, full_response

def gemini_completion(system_prompt, model_name, base64_image, prompt):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel(model_name=model_name)

    messages = [
        {
            "mime_type": "image/jpeg",
            "data": base64_image,
        },
        prompt,
    ]
            
    try:
        response = model.generate_content(
            messages,
        )
    except Exception as e:
        print(f"error: {e}")
        return "error", "error: " + str(e)

    full_response = response.text
    generated_code_str = extract_code(full_response)

    return generated_code_str, full_response