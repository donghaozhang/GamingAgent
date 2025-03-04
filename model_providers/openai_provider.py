import os
import sys
import base64
from openai import OpenAI
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

class OpenAIProvider:
    """
    Provider class for OpenAI GPT-4o API integration.
    This class provides integration with OpenAI's latest models for the Tetris agent.
    """
    
    def __init__(self, model="gpt-4o"):
        """
        Initialize the OpenAI provider with the specified model.
        
        Args:
            model (str): The name of the OpenAI model to use. Default is gpt-4o.
        """
        self.model = model
        # Verify API key is available
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set. Please check your .env file.")
        
        # Initialize the OpenAI client
        self.client = OpenAI(api_key=self.api_key)
        
    def get_response(self, prompt, image_data=None):
        """
        Get a response from the OpenAI model.
        
        Args:
            prompt (str): The text prompt to send to the model.
            image_data (bytes, optional): PNG image data if available.
            
        Returns:
            str: The model's response text.
        """
        # Create content array
        messages = []
        
        # Setup system prompt for Tetris
        system_prompt = """You are an AI assistant that helps play Tetris. 
        Analyze the current game state and suggest the best move for the current piece.
        Focus on clearing lines and building a stable stack.
        MAKE DECISIONS QUICKLY AND BE DECISIVE! The game requires fast reactions.
        Immediately determine the best action for the current piece.
        Express your decision as direct key presses (LEFT, RIGHT, UP for rotation, DOWN for fast drop).
        Multiple actions in sequence are fine, but ACT QUICKLY!
        Respond with a clear action using pygame key constants (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN)."""
        
        # Add system message
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # Create the user message content
        content = []
        
        # Add image to content if provided
        if image_data is not None and isinstance(image_data, bytes):
            try:
                # Convert binary image data to base64
                base64_image = base64.b64encode(image_data).decode('utf-8')
                
                # Add image to content
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}"
                    }
                })
                
                # Add text after image
                content.append({
                    "type": "text",
                    "text": prompt
                })
                
                # Add complete message with both image and text
                messages.append({
                    "role": "user",
                    "content": content
                })
            except Exception as e:
                print(f"Error processing image: {e}")
                # Fallback to text-only if image processing fails
                messages.append({
                    "role": "user",
                    "content": prompt
                })
        else:
            # Text-only message
            messages.append({
                "role": "user",
                "content": prompt
            })
        
        try:
            # Call the OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=100,
            )
            
            # Extract the response text
            response_text = response.choices[0].message.content
            return response_text
            
        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return "I'll use pygame.K_DOWN to move the piece down faster."  # Fallback response 