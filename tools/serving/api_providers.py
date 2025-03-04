import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from openai import OpenAI
import anthropic
import google.generativeai as genai

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
    import time
    
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
    
    try:
        print("Starting Anthropic API call...")
        # Use a non-streaming version with timeout
        response = client.messages.create(
                max_tokens=1024,
                messages=messages,
                temperature=0,
                system=system_prompt,
                model=model_name,
                timeout=30  # 30 second timeout
            )
        
        print("Anthropic API call completed successfully")
        generated_code_str = response.content[0].text
        
    except Exception as e:
        print(f"Error during Anthropic API call: {e}")
        # Return a simple fallback response if API call fails
        generated_code_str = """
        # Fallback response due to API timeout or error
        # Moving tetris piece to a safe position
        import pyautogui
        import time
        
        # Move left to center piece
        pyautogui.press('left')
        time.sleep(0.2)
        
        # Rotate if needed
        pyautogui.press('up')
        time.sleep(0.2)
        
        # Drop the piece
        pyautogui.press('space')
        """
    
    return generated_code_str

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

    generated_code_str = response.text

    return generated_code_str