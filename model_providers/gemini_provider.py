import os
import sys
import base64
import google.generativeai as genai
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

class GeminiProvider:
    """
    Provider class for Google Gemini API integration.
    This class provides integration with Google's Gemini models for the Tetris agent.
    """
    
    def __init__(self, model="gemini-flash-2.0"):
        """
        Initialize the Gemini provider with the specified model.
        
        Args:
            model (str): The name of the Gemini model to use. Default is gemini-flash-2.0.
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
        
    def get_response(self, prompt, image_data=None):
        """
        Get a response from the Gemini model.
        
        Args:
            prompt (str): The text prompt to send to the model.
            image_data (bytes, optional): PNG image data if available.
            
        Returns:
            str: The model's response text.
        """
        # Setup system prompt for Tetris
        system_prompt = """You are an AI assistant that helps play Tetris. 
        BE EXTREMELY BRIEF AND DECISIVE! Analyze the game state and immediately determine the optimal move.
        Express your decision using ONLY pygame key constants (K_LEFT, K_RIGHT, K_UP, K_DOWN).
        DO NOT explain your reasoning - JUST GIVE THE MOVES like this:
        "K_LEFT K_LEFT K_UP K_DOWN"
        Your response must only contain key constants with spaces between them.
        SPEED IS CRITICAL, so be extremely concise."""
        
        try:
            # Prepare the content
            contents = []
            
            # Add system prompt
            contents.append(system_prompt)
            
            # Add image if provided
            if image_data is not None and isinstance(image_data, bytes):
                try:
                    # Convert binary data to PIL image
                    image = Image.open(BytesIO(image_data))
                    contents.append(image)
                except Exception as e:
                    print(f"Error processing image: {e}")
            
            # Add text prompt
            contents.append(prompt)
            
            # Generate response from the model
            generation_config = {
                "temperature": 0.2,
                "max_output_tokens": 100
            }
            
            response = self.genai_model.generate_content(
                contents,
                generation_config=generation_config,
                safety_settings=None
            )
            
            # Extract and return the text content
            return response.text
            
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            return "I'll use pygame.K_DOWN to move the piece down faster."  # Fallback response 