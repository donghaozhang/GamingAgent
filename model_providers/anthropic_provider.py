import os
import sys
import base64
import anthropic
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

class AnthropicProvider:
    """
    Provider class for Anthropic Claude API integration.
    This class adapts the existing anthropic_completion function for the Tetris agent.
    """
    
    def __init__(self, model="claude-3-7-sonnet-20250219"):
        """
        Initialize the Anthropic provider with the specified model.
        
        Args:
            model (str): The name of the Anthropic model to use.
        """
        self.model = model
        # Verify API key is available
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set. Please check your .env file.")
        
        # Initialize the Anthropic client
        self.client = anthropic.Anthropic(api_key=self.api_key)
        
    def get_response(self, prompt, image_data=None):
        """
        Get a response from the Anthropic model.
        
        Args:
            prompt (str): The text prompt to send to the model.
            image_data (bytes, optional): PNG image data if available.
            
        Returns:
            str: The model's response text.
        """
        # Create content array
        content = []
        
        # Add image to content if provided
        if image_data is not None and isinstance(image_data, bytes):
            try:
                # Convert binary image data to base64
                base64_image = base64.b64encode(image_data).decode('utf-8')
                
                # Add image to content
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64_image,
                    },
                })
            except Exception as e:
                print(f"Error processing image: {e}")
        
        # Add text prompt to content
        content.append({
            "type": "text",
            "text": prompt
        })
        
        # Create messages
        messages = [
            {
                "role": "user",
                "content": content,
            }
        ]
        
        # Setup system prompt for Tetris
        system_prompt = """You are an AI assistant that helps play Tetris. 
        Analyze the current game state and suggest the best move for the current piece.
        Focus on clearing lines and building a stable stack.
        
        ### Strategies:
        1. Prioritize keeping the stack flat and balanced
        2. Avoid creating holes
        3. Clear lines when possible
        4. Plan ahead for the next piece
        
        ### Controls:
        - pygame.K_LEFT: move piece left
        - pygame.K_RIGHT: move piece right
        - pygame.K_UP: rotate piece clockwise
        - pygame.K_DOWN: accelerated drop
        
        Express your moves using pygame key constants (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN).
        Be quick and decisive - the game requires fast reactions!"""
        
        try:
            # Stream response from the model
            with self.client.messages.stream(
                max_tokens=100,
                messages=messages,
                temperature=0.2,
                system=system_prompt,
                model=self.model,
            ) as stream:
                partial_chunks = []
                for chunk in stream.text_stream:
                    partial_chunks.append(chunk)
            
            # Join all chunks into the final response
            response = "".join(partial_chunks)
            return response
            
        except Exception as e:
            print(f"Error calling Anthropic API: {e}")
            return "I'll use pygame.K_DOWN to move the piece down faster."  # Fallback response 