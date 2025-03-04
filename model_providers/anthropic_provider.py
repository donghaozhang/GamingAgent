import os
import sys
import base64
import anthropic
from dotenv import load_dotenv
import random

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
        
    def get_response(self, prompt, base64_image=None):
        """
        Get a response from the Anthropic model.
        
        Args:
            prompt (str): The text prompt to send to the model.
            base64_image (str, optional): Base64-encoded image data.
            
        Returns:
            str: The model's response text.
        """
        # Create content array
        content = []
        
        # Add image to content if provided
        if base64_image:
            try:
                # If the base64 string has a data URL prefix, remove it
                if ',' in base64_image:
                    base64_image = base64_image.split(',', 1)[1]
                
                # Add image to content
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64_image,
                    },
                })
                print(f"Added image to Anthropic request, content array length: {len(content)}")
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
        system_prompt = """
        Analyze the current Tetris board state and generate PyAutoGUI code to control Tetris 
        for the next {plan_seconds} second(s). You can move left/right, rotate pieces. Focus on clearing lines and avoiding 
        stacking that would cause a top-out.

        At the time the code is executed, 3~5 seconds have elapsed. The game might have moved on to the next block if the stack is high.

        However, in your code, consider only the current block or the next block.

        The speed it drops is at around ~0.75s/grid bock.

        ### General Tetris Controls (example keybinds):
        - left: move piece left
        - right: move piece right
        - up: rotate piece clockwise
        - down: accelerated drop （if necessary)

        ### Strategies and Caveats:
        1. If the stack is high, most likely you are controlling the "next" block due to latency.
        2. Prioritize keeping the stack flat. Balance the two sides.
        3. Consider shapes ahead of time. DO NOT rotate and quickly move the block again once it's position is decided.
        4. Avoid creating holes.
        5. If you see a chance to clear lines, rotate and move the block to correct positions.
        6. Plan for your next piece as well, but do not top out.
        7. The entire sequence of key presses should be feasible within {plan_seconds} second(s).

        ### Output Format:
        - Output ONLY the Python code for PyAutoGUI commands, e.g. `pyautogui.press("left")`.
        - Include brief comments for each action.
        - Do not print anything else besides these Python commands.
        """
        
        try:
            # Call the Anthropic API
            response = self.client.messages.create(
                model=self.model,
                system=system_prompt,
                messages=messages,
                max_tokens=30000,
                temperature=0.2,
            )
            
            # Return the text from the response
            if hasattr(response, 'content') and len(response.content) > 0:
                # Extract text content from the response
                text_content = ''
                for item in response.content:
                    if item.type == 'text':
                        text_content += item.text
                return text_content
            return "No valid response from Claude"
        
        except Exception as e:
            # Print the error for debugging
            print(f"Error calling Anthropic API: {e}")
            
            # Fallback responses for when the API call fails
            fallback_responses = [
                "I'll use pygame.K_LEFT to move the piece left.",
                "I'll use pygame.K_RIGHT to move the piece right.",
                "I'll use pygame.K_UP to rotate the piece.",
                "I'll use pygame.K_DOWN to move the piece down faster."
            ]
            return random.choice(fallback_responses) 