import os
import sys

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from openai import OpenAI
import anthropic
import google.generativeai as genai
from model_providers.gemini_provider import GeminiProvider

def openai_completion(system_prompt, model_name, base64_image, prompt):
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
    # Create or get the provider (could be cached for performance)
    provider = GeminiProvider(model=model_name)
    
    # Get completion directly from the provider
    generated_code_str = provider.get_completion(
        system_prompt=system_prompt,
        prompt=prompt,
        base64_image=base64_image
    )
    
    return generated_code_str