import os
import sys
import base64
import google.generativeai as genai
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv
import random

# Ensure environment variables are loaded
load_dotenv()

class GeminiProvider:
    """
    Provider class for Google Gemini API integration.
    This class provides integration with Google's Gemini models for the Tetris agent.
    """
    
    def __init__(self, model="gemini-1.5-pro"):
        """
        Initialize the Gemini provider with the specified model.
        
        Args:
            model (str): The name of the Gemini model to use. Default is gemini-1.5-flash.
        """
        self.model = model
        # Verify API key is available
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set. Please check your .env file.")
        
        # Configure the Gemini API
        genai.configure(api_key=self.api_key)
        
        # Get the model
        self.genai_model = genai.GenerativeModel(self.model)
        
    def get_response(self, prompt, image_data=None, image_path=None):
        """
        Get a response from the Gemini model.
        
        Args:
            prompt (str): The text prompt to send to the model.
            image_data (bytes, optional): PNG image data if available.
            image_path (str, optional): Path to image file if available.
            
        Returns:
            str: The model's response text.
        """
        # Setup system prompt for Tetris
        system_prompt = """You are an AI assistant that helps play Tetris. 
        BE EXTREMELY BRIEF AND DECISIVE! Analyze the game state and immediately determine the optimal move.
        
        ### Strategies:
        1. Keep the stack flat horizontal not verticaland balanced
        2. Avoid creating holes
        3. Clear lines when possible
        4. Plan ahead for the next piece
        
        ### Controls:
        - K_LEFT: move piece left
        - K_RIGHT: move piece right
        - K_UP: rotate piece clockwise
        - K_DOWN: accelerated drop
        
        Express your moves using ONLY key constants (K_LEFT, K_RIGHT, K_UP, K_DOWN).
        Your response must only contain key constants with spaces between them.
        SPEED IS CRITICAL, so be extremely concise."""
        
        try:
            # Prepare content correctly for Gemini API
            contents = []
            
            # Handle image input - either from binary data or file path
            if image_path and os.path.exists(image_path):
                encoded_image = self.encode_image(image_path)
                # For API that requires base64 encoding
                # Here you would use the encoded_image variable
                
                # For the google-generativeai library, we can load the image directly
                image = Image.open(image_path)
                contents.append(image)
            elif image_data is not None and isinstance(image_data, bytes):
                try:
                    # Convert binary data to PIL image
                    image = Image.open(BytesIO(image_data))
                    # Add image to contents
                    contents.append(image)
                except Exception as e:
                    print(f"Error processing image: {e}")
            
            # Add the text after the image if present
            contents.append(f"{system_prompt}\n\n{prompt}")
            
            # Generate response from the model
            generation_config = {
                "temperature": 0.2,
                "max_output_tokens": 1000
            }
            
            response = self.genai_model.generate_content(
                contents,
                generation_config=generation_config
            )
            print(f"Gemini Response: {response.text}")
            # Extract and return the text content
            return response.text
            
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            # Return a random fallback response to avoid always using DOWN
            fallback_responses = [
                "I'll use pygame.K_LEFT to move the piece left.",
                "I'll use pygame.K_RIGHT to move the piece right.",
                "I'll use pygame.K_UP to rotate the piece.",
                "I'll use pygame.K_DOWN to move the piece down faster."
            ]
            return random.choice(fallback_responses) 

    def encode_image(self, image_path):
        """
        Read a file from disk and return its contents as a base64-encoded string.
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    
    def get_completion(self, system_prompt, prompt, base64_image=None):
        """
        Get a completion from the Gemini model, compatible with the worker_tetris function format.
        
        Args:
            system_prompt (str): The system instructions for the model.
            prompt (str): The text prompt to send to the model.
            base64_image (str, optional): Base64-encoded image data.
            
        Returns:
            str: The model's response text.
        """
        try:
            # Prepare content for the model
            content_parts = []
            
            # Add image if provided
            if base64_image:
                try:
                    # Convert base64 to binary
                    image_bytes = base64.b64decode(base64_image)
                    image = Image.open(BytesIO(image_bytes))
                    
                    # Add image to content parts
                    content_parts.append(image)
                except Exception as e:
                    print(f"Error processing image: {e}")
            
            # Combine system prompt with user prompt
            combined_prompt = f"{system_prompt}\n\n{prompt}"
            content_parts.append(combined_prompt)
            
            # Generate response from the model
            generation_config = {
                "temperature": 0.2,
                "max_output_tokens": 1024
            }
            
            response = self.genai_model.generate_content(
                content_parts,
                generation_config=generation_config
            )
            
            print(f"Gemini Response: {response.text[:100]}...")  # Print first 100 chars of response
            return response.text
            
        except Exception as e:
            print(f"Error generating Gemini response: {e}")
            # Return a fallback that won't crash when executed
            return """
            # API call failed, executing fallback moves
            import time
            # Move slightly left and right to keep the game going
            pyautogui.press("left")
            time.sleep(0.2)
            pyautogui.press("right")
            """ 