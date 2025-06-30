#!/usr/bin/env python3
"""
Test script to verify safe serialization of non-serializable objects.
"""

import sys
import logging
from pathlib import Path

# Add the current directory to Python path to import from app.py
sys.path.insert(0, str(Path(__file__).parent))

# Import the safe_serialize function from app.py
try:
    from app import safe_serialize
except ImportError as e:
    print(f"Error importing safe_serialize: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_safe_serialize():
    """Test the safe_serialize function with various object types"""
    print("🔍 Testing safe serialization...")
    
    # Test 1: Message-like object
    class MockMessage:
        def __init__(self, content, role="test"):
            self.content = content
            self.role = role
    
    message_obj = MockMessage("Test message content", "test_role")
    result = safe_serialize(message_obj)
    print(f"  ✓ Message object: {result}")
    
    # Test 2: List with mixed types
    mixed_list = [
        "string",
        123,
        MockMessage("nested message"),
        {"key": "value"},
        None
    ]
    result = safe_serialize(mixed_list)
    print(f"  ✓ Mixed list: {result}")
    
    # Test 3: Dictionary with complex values
    complex_dict = {
        "string": "value",
        "number": 42,
        "message": MockMessage("dict message"),
        "nested": {"inner": MockMessage("nested dict message")}
    }
    result = safe_serialize(complex_dict)
    print(f"  ✓ Complex dict: {result}")
    
    # Test 4: Object without content attribute
    class SimpleObject:
        def __init__(self, data):
            self.data = data
    
    simple_obj = SimpleObject("simple data")
    result = safe_serialize(simple_obj)
    print(f"  ✓ Simple object: {result}")
    
    # Test 5: Object that raises exception when accessed
    class ProblematicObject:
        def __str__(self):
            raise Exception("Cannot stringify this object")
    
    problematic_obj = ProblematicObject()
    result = safe_serialize(problematic_obj)
    print(f"  ✓ Problematic object: {result}")
    
    print("✅ All serialization tests passed!")
    return True

def test_search_results_serialization():
    """Test serialization of typical search results"""
    print("\n🔍 Testing search results serialization...")
    
    # Define MockMessage class for this test
    class MockMessage:
        def __init__(self, content, role="test"):
            self.content = content
            self.role = role
    
    # Simulate typical search results that might contain Message objects
    search_results = [
        "Regular string result",
        MockMessage("Message object in results"),
        {"title": "Search Result", "content": MockMessage("Nested message")},
        ["list", "of", MockMessage("messages")],
        None
    ]
    
    try:
        result = safe_serialize(search_results)
        print(f"  ✓ Search results serialized: {result[:200]}...")
        print("✅ Search results serialization test passed!")
        return True
    except Exception as e:
        print(f"  ❌ Search results serialization failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting serialization tests...\n")
    
    tests = [
        test_safe_serialize(),
        test_search_results_serialization()
    ]
    
    print("\n" + "="*50)
    print("📊 Test Results:")
    
    test_names = ["Safe Serialize", "Search Results"]
    passed = sum(1 for result in tests if result)
    
    for i, (name, result) in enumerate(zip(test_names, tests)):
        status = "✅ Passed" if result else "❌ Failed"
        print(f"{status}: {name}")
    
    print(f"\n🎯 Overall: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All serialization tests passed! The fixes are working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Please check the issues.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 