import os
import sys
import base64
from openai import OpenAI
from dotenv import load_dotenv
import random

# Ensure environment variables are loaded
load_dotenv()

class OpenRouterProvider:
    """
    Provider class for OpenRouter API integration.
    This class allows access to various LLMs, including Claude 3.7, through the OpenRouter API.
    """
    
    def __init__(self, model="anthropic/claude-3-7-sonnet:thinking"):
        """
        Initialize the OpenRouter provider with the specified model.
        
        Args:
            model (str): The name of the model to use on OpenRouter, default is Claude 3.7 Sonnet (thinking).
                        Format: "provider/model" - e.g., "anthropic/claude-3-7-sonnet:thinking"
        """
        self.model = model
        # Verify API key is available
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set. Please check your .env file.")
        
        # Initialize the OpenAI client with OpenRouter base URL and default headers
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/lmgame-org/GamingAgent"  # Site URL for OpenRouter
            }
        )
        
    def get_response(self, prompt, base64_image=None):
        """
        Get a response from the model through OpenRouter API.
        
        Args:
            prompt (str): The text prompt to send to the model.
            base64_image (str, optional): Base64-encoded image data.
            
        Returns:
            str: The model's response text.
        """
        # Create a messages array for the API request
        messages = []
        
        # Create content array to hold image and text if Claude model
        if "anthropic/claude" in self.model:
            # Claude format with content array
            content = []
            
            # Add image to content if provided
            if base64_image:
                try:
                    # If the base64 string has a data URL prefix, remove it
                    if ',' in base64_image:
                        base64_image = base64_image.split(',', 1)[1]
                    
                    # Add image to content array in Claude format
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": base64_image,
                        },
                    })
                    print(f"Added image to OpenRouter request for Claude, content array length: {len(content)}")
                except Exception as e:
                    print(f"Error processing image: {e}")
            
            # Add text prompt to content
            content.append({
                "type": "text",
                "text": prompt
            })
            
            # Add the message with content array
            messages.append({
                "role": "user",
                "content": content
            })
        else:
            # For non-Claude models use standard OpenAI format
            message_content = []
            
            # Add text content
            message_content.append({
                "type": "text", 
                "text": prompt
            })
            
            # Add image if provided
            if base64_image:
                try:
                    # Add full data URL if not present
                    if not base64_image.startswith("data:"):
                        base64_image = f"data:image/png;base64,{base64_image}"
                        
                    # Add image in OpenAI format
                    message_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": base64_image
                        }
                    })
                    print(f"Added image to OpenRouter request, content array length: {len(message_content)}")
                except Exception as e:
                    print(f"Error processing image: {e}")
            
            # Add message with content
            messages.append({
                "role": "user",
                "content": message_content
            })
        
        # System prompt for Tetris
        system_prompt = """You are an AI assistant that helps play Tetris. 
        Analyze the current game state and suggest the best move for the current piece.
        Return valid Pygame key constants (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN) to move the current piece.
        LEFT and RIGHT to move, UP to rotate, DOWN to drop faster.
        Your goal is to clear as many lines as possible."""
        
        try:
            # Call the OpenRouter API using OpenAI client format
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *messages
                ],
                max_tokens=1024,
                temperature=0.2
            )
            
            # Return the text from the response
            if hasattr(response, 'choices') and len(response.choices) > 0:
                return response.choices[0].message.content
            return "No valid response from OpenRouter"
        
        except Exception as e:
            # Print the error for debugging
            print(f"Error calling OpenRouter API: {e}")
            
            # Fallback responses for when the API call fails
            fallback_responses = [
                "I'll use pygame.K_LEFT to move the piece left.",
                "I'll use pygame.K_RIGHT to move the piece right.",
                "I'll use pygame.K_UP to rotate the piece.",
                "I'll use pygame.K_DOWN to move the piece down faster."
            ]
            return random.choice(fallback_responses)
    
    def get_completion(self, system_prompt, prompt, base64_image=None):
        """
        Get a completion from the model, compatible with the worker_tetris function format.
        
        Args:
            system_prompt (str): The system prompt to use.
            prompt (str): The text prompt to send to the model.
            base64_image (str, optional): Base64-encoded image data.
            
        Returns:
            str: The model's response text.
        """
        messages = []
        
        # Create content array for Claude models
        if "anthropic/claude" in self.model:
            content = []
            
            # Add image to content if provided
            if base64_image:
                try:
                    # If the base64 string has a data URL prefix, remove it
                    if ',' in base64_image:
                        base64_image = base64_image.split(',', 1)[1]
                    
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
            
            messages.append({
                "role": "user",
                "content": content
            })
        else:
            # For non-Claude models
            message_content = []
            
            # Add text content
            message_content.append({
                "type": "text", 
                "text": prompt
            })
            
            # Add image if provided
            if base64_image:
                try:
                    # Add full data URL if not present
                    if not base64_image.startswith("data:"):
                        base64_image = f"data:image/png;base64,{base64_image}"
                        
                    message_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": base64_image
                        }
                    })
                except Exception as e:
                    print(f"Error processing image: {e}")
            
            messages.append({
                "role": "user",
                "content": message_content
            })
        
        try:
            # Call the OpenRouter API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *messages
                ],
                max_tokens=1024,
                temperature=0.2
            )
            print('OpenRouter Response: ', response)
            # Return the text from the response
            if hasattr(response, 'choices') and len(response.choices) > 0:
                return response.choices[0].message.content
            return "No valid response from OpenRouter"
        
        except Exception as e:
            print(f"Error calling OpenRouter API: {e}")
            
            # Fallback responses for when the API call fails
            fallback_responses = [
                "I'll use pygame.K_LEFT to move the piece left.",
                "I'll use pygame.K_RIGHT to move the piece right.",
                "I'll use pygame.K_UP to rotate the piece.",
                "I'll use pygame.K_DOWN to move the piece down faster."
            ]
            return random.choice(fallback_responses) 