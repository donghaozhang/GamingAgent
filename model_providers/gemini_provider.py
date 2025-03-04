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
        
    def get_response(self, prompt, base64_image=None, image_path=None):
        """
        Get a response from the Gemini model.
        
        Args:
            prompt (str): The text prompt to send to the model.
            base64_image (str, optional): Base64-encoded image data.
            image_path (str, optional): Path to image file if available.
            
        Returns:
            str: The model's response text.
        """
        # Setup system prompt for Tetris
        system_prompt = """You are an AI assistant that helps play Tetris. 
        Analyze the current game state and suggest the best move for the current piece.
        Return valid Pygame key constants (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN) to move the current piece.
        LEFT and RIGHT to move, UP to rotate, DOWN to drop faster.
        Your goal is to clear as many lines as possible."""
        
        try:
            # Prepare contents
            contents = []
            
            # Add system prompt
            contents.append(system_prompt)
            
            # Add image if provided
            if base64_image:
                try:
                    # If the base64 string has a data URL prefix, remove it
                    if ',' in base64_image:
                        base64_image = base64_image.split(',', 1)[1]
                    
                    # Decode base64 to binary
                    image_bytes = base64.b64decode(base64_image)
                    
                    # Open the image
                    image = Image.open(BytesIO(image_bytes))
                    
                    # Add the image to contents
                    contents.append(image)
                    print(f"Added image to Gemini request, content array length: {len(contents)}")
                except Exception as e:
                    print(f"Error processing image for Gemini: {e}")
            elif image_path:
                # Use image from file path
                encoded_image = self.encode_image(image_path)
                contents.append(encoded_image)
                print(f"Added image from path to Gemini request, content array length: {len(contents)}")
            
            # Add the prompt text
            contents.append(prompt)
            
            # Configure generation parameters
            generation_config = {
                "temperature": 0.2,
                "top_p": 0.95,
                "top_k": 32,
                "max_output_tokens": 1024,
            }
            
            # Call the Gemini API
            response = self.genai_model.generate_content(
                contents,
                generation_config=generation_config
            )
            
            # Return the response text
            if hasattr(response, 'text'):
                return response.text
            return str(response)
        
        except Exception as e:
            # Print the error for debugging
            print(f"Error calling Gemini API: {e}")
            
            # Fallback responses for when the API call fails
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