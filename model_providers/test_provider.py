from anthropic_provider import AnthropicProvider
from openai_provider import OpenAIProvider
from gemini_provider import GeminiProvider
from openrouter_provider import OpenRouterProvider

def test_anthropic_provider():
    """
    Simple test for the AnthropicProvider to verify it can connect to the API.
    """
    try:
        # Create the provider
        provider = AnthropicProvider()
        print(f"Successfully created provider with model: {provider.model}")
        
        # Test a simple response
        test_prompt = "In Tetris, I have an 'L' piece and there's a gap on the right side of the board. What should I do?"
        print(f"Sending test prompt: {test_prompt}")
        
        response = provider.get_response(test_prompt)
        print(f"Received response: {response}")
        
        return True
    except Exception as e:
        print(f"Error testing AnthropicProvider: {e}")
        return False

def test_openai_provider():
    """
    Simple test for the OpenAIProvider to verify it can connect to the API.
    """
    try:
        # Create the provider
        provider = OpenAIProvider()
        print(f"Successfully created provider with model: {provider.model}")
        
        # Test a simple response
        test_prompt = "In Tetris, I have an 'L' piece and there's a gap on the right side of the board. What should I do?"
        print(f"Sending test prompt: {test_prompt}")
        
        response = provider.get_response(test_prompt)
        print(f"Received response: {response}")
        
        return True
    except Exception as e:
        print(f"Error testing OpenAIProvider: {e}")
        return False

def test_gemini_provider():
    """
    Simple test for the GeminiProvider to verify it can connect to the API.
    Tests with the fast Gemini Flash 2.0 model.
    """
    try:
        # Create the provider
        provider = GeminiProvider()
        print(f"Successfully created provider with model: {provider.model}")
        
        # Test a simple response
        # test_prompt = "In Tetris, I have an 'L' piece and there's a gap on the right side of the board. What should I do?"
        test_prompt = "What model are you and bespecifically what is your model name?"
        print(f"Sending test prompt: {test_prompt}")
        
        response = provider.get_response(test_prompt)
        print(f"Received response: {response}")
        
        return True
    except Exception as e:
        print(f"Error testing GeminiProvider: {e}")
        return False

def test_openrouter_provider():
    """
    Simple test for the OpenRouterProvider to verify it can connect to the API.
    Tests with the Claude 3.7 Sonnet (thinking) model via OpenRouter.
    """
    try:
        # Create the provider
        provider = OpenRouterProvider(model="anthropic/claude-3.7-sonnet")
        print(f"Successfully created provider with model: {provider.model}")
        
        # Test a simple response
        test_prompt = "What model are you? Please specify your full name and capabilities."
        print(f"Sending test prompt to OpenRouter: {test_prompt}")
        
        print("Calling OpenRouter API...")
        response = provider.get_response(test_prompt)
        print("\n--- FULL RESPONSE FROM OPENROUTER ---")
        print(response)
        print("--- END OF RESPONSE ---\n")
        
        # Print the first 100 characters of the response for a quick view
        if response:
            preview = response[:100] + "..." if len(response) > 100 else response
            print(f"Response preview: {preview}")
        else:
            print("No response received from OpenRouter")
        
        return True
    except Exception as e:
        print(f"Error testing OpenRouterProvider: {e}")
        return False

if __name__ == "__main__":
    # Test Anthropic Provider
    print("Testing AnthropicProvider...")
    anthropic_success = test_anthropic_provider()
    
    if anthropic_success:
        print("Anthropic test completed successfully!")
    else:
        print("Anthropic test failed.")
        
    # Test OpenAI Provider
    print("\nTesting OpenAIProvider...")
    openai_success = test_openai_provider()
    
    if openai_success:
        print("OpenAI test completed successfully!")
    else:
        print("OpenAI test failed.")
        
    # Test Gemini Provider
    print("\nTesting GeminiProvider...")
    gemini_success = test_gemini_provider()
    
    if gemini_success:
        print("Gemini test completed successfully!")
    else:
        print("Gemini test failed.")
        
    # Test OpenRouter Provider
    print("\nTesting OpenRouterProvider...")
    openrouter_success = test_openrouter_provider()
    
    if openrouter_success:
        print("OpenRouter test completed successfully!")
    else:
        print("OpenRouter test failed.") 