"""
Quick test script to verify Gemini API is working.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add app to path
sys.path.insert(0, os.path.dirname(__file__))

def test_gemini_basic():
    """Test basic Gemini API connectivity."""
    print("=" * 60)
    print("Testing Gemini API Configuration")
    print("=" * 60)
    
    # Check API key
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not found in environment")
        return False
    
    print(f"✓ API Key found: {api_key[:20]}...")
    
    # Try importing the package
    try:
        import google.generativeai as genai
        print("✓ google-generativeai package imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import google-generativeai: {e}")
        return False
    
    # Configure and test
    try:
        genai.configure(api_key=api_key)
        print("✓ API configured successfully")
        
        # List models to verify connection
        print("\nFetching available models...")
        models = list(genai.list_models())
        print(f"✓ Successfully fetched {len(models)} models")
        
        # Show some models
        print("\nAvailable models (first 10):")
        for i, model in enumerate(models[:10]):
            print(f"  {i+1}. {model.name}")
        
        return True
        
    except Exception as e:
        print(f"❌ API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gemini_generation():
    """Test Gemini generation with structured outputs."""
    print("\n" + "=" * 60)
    print("Testing Gemini Structured Output Generation")
    print("=" * 60)
    
    try:
        import google.generativeai as genai
        from google.generativeai.types import GenerationConfig
        
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=api_key)
        
        # Simple test schema
        test_schema = {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "The title of the company"
                },
                "summary": {
                    "type": "STRING",
                    "description": "A brief summary"
                }
            },
            "required": ["title", "summary"]
        }
        
        # Try generation with structured output
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-exp",
            generation_config=GenerationConfig(
                temperature=1.0,
                max_output_tokens=1024,
                response_mime_type="application/json",
                response_schema=test_schema,
            ),
        )
        
        print("\nGenerating test content...")
        prompt = "Tell me about Apple Inc. in JSON format."
        
        response = model.generate_content(prompt)
        
        if response.text:
            print("✓ Generation successful!")
            print(f"\nResponse:\n{response.text[:500]}")
            
            # Check if it's valid JSON
            import json
            try:
                parsed = json.loads(response.text)
                print("\n✓ Valid JSON response")
                print(f"  - title: {parsed.get('title', 'N/A')}")
                print(f"  - summary: {parsed.get('summary', 'N/A')[:100]}...")
                return True
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON: {e}")
                return False
        else:
            print("❌ No response text")
            return False
            
    except Exception as e:
        print(f"❌ Generation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gemini_provider():
    """Test the GeminiProvider class."""
    print("\n" + "=" * 60)
    print("Testing GeminiProvider Implementation")
    print("=" * 60)
    
    try:
        from app.deck.services.llm_gemini import GeminiProvider
        from app.deck.services.llm_base import LLMOptions
        
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        
        # Initialize provider
        provider = GeminiProvider(api_key=api_key)
        print("✓ GeminiProvider initialized")
        
        # Validate API key
        is_valid = provider.validate_api_key()
        if is_valid:
            print("✓ API key validation successful")
        else:
            print("❌ API key validation failed")
            return False
        
        # Test schema conversion
        json_schema = {
            "type": "object",
            "properties": {
                "company": {"type": "string"},
                "year": {"type": "integer"}
            }
        }
        
        gemini_schema = provider._convert_to_gemini_schema(json_schema)
        print(f"✓ Schema conversion working")
        print(f"  Converted schema: {gemini_schema}")
        
        # Test actual generation
        print("\nTesting generation...")
        response = provider.generate_json(
            system_prompt="You are a helpful assistant.",
            user_prompt="Tell me about Tesla in JSON format.",
            json_schema={
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "Company name"},
                    "industry": {"type": "string", "description": "Industry"}
                },
                "required": ["company", "industry"]
            },
            options=LLMOptions(timeout=30)
        )
        
        print("✓ Generation successful!")
        print(f"  - Provider: {response.provider}")
        print(f"  - Model: {response.model}")
        print(f"  - Latency: {response.latency_ms:.2f}ms")
        print(f"  - Content: {response.content}")
        
        return True
        
    except Exception as e:
        print(f"❌ Provider test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n🔍 Gemini API Test Suite\n")
    
    results = []
    
    # Test 1: Basic connectivity
    results.append(("Basic API Test", test_gemini_basic()))
    
    # Test 2: Generation
    results.append(("Generation Test", test_gemini_generation()))
    
    # Test 3: Provider implementation
    results.append(("Provider Test", test_gemini_provider()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n✓ All tests passed! Gemini API is working correctly.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Check the output above for details.")
        sys.exit(1)
