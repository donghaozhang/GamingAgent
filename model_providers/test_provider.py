from anthropic_provider import AnthropicProvider

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

if __name__ == "__main__":
    print("Testing AnthropicProvider...")
    success = test_anthropic_provider()
    
    if success:
        print("Test completed successfully!")
    else:
        print("Test failed.") 