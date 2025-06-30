#!/usr/bin/env python3
"""
Test script to demonstrate the search functionality and logging
"""
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_search_functionality():
    """Test the search functionality"""
    print("🔍 Testing Search Functionality")
    print("=" * 50)
    
    # Check if SERPER_API_KEY is set
    serper_api_key = os.getenv("SERPER_API_KEY")
    if not serper_api_key:
        print("❌ SERPER_API_KEY not found in environment variables")
        print("💡 To enable web search, add SERPER_API_KEY to your .env file")
        print("   Get your API key from: https://serper.dev/")
        return
    
    print("✅ SERPER_API_KEY found")
    
    try:
        # Import the search functionality
        from app import SearchWeb
        
        # Create a search instance
        search_action = SearchWeb()
        
        # Test search
        test_query = "latest React.js best practices 2024"
        print(f"🔍 Testing search for: {test_query}")
        
        result = await search_action.run(test_query, max_results=3, agent_name="Test Agent")
        print(f"✅ Search completed successfully")
        print(f"📄 Results preview: {result[:200]}...")
        
    except Exception as e:
        print(f"❌ Search test failed: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 To see search activities in action, run:")
    print("   chainlit run app.py")
    print("   Then describe a project and watch the agents search the web!")

if __name__ == "__main__":
    asyncio.run(test_search_functionality()) 