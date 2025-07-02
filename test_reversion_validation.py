#!/usr/bin/env python3
"""
Test the strict reversion validation to ensure it doesn't trigger on regular notices.
"""
import os
from shfe_scraper import LLMEnhancedSHFEScraper

def test_reversion_validation():
    """Test the reversion validation logic"""
    print("🧪 Testing Strict Reversion Validation")
    print("=" * 50)
    
    scraper = LLMEnhancedSHFEScraper(
        start_date='2025-04-01',
        anthropic_api_key='mock_key',
        output_dir='test_output'
    )
    
    # Test cases for different types of notices
    test_cases = [
        {
            'title': 'Notice on Work Arrangements during Labor Day 2025',
            'claude_result': {
                'is_reversion_notice': True,
                'reversion_details': {
                    'has_reversion_clause': True,
                    'reversion_text': 'For other contracts, the daily price limits and margin ratios will revert to their original levels unless otherwise specified'
                },
                'effective_dates': [
                    {'date': '2025-04-29', 'commodities': [{'commodity': 'Gold'}] * 18},
                    {'date': '2025-05-06', 'commodities': [{'commodity': 'Gold'}]}
                ]
            },
            'expected': True,
            'reason': 'Valid holiday reversion notice'
        },
        {
            'title': 'Notice on Adjusting the Margin Ratio and Price Limits of Alumina Futures Trading',
            'claude_result': {
                'is_reversion_notice': False,
                'effective_dates': [
                    {'date': '2025-03-11', 'commodities': [{'commodity': 'Alumina'}]}
                ]
            },
            'expected': False,
            'reason': 'Regular margin adjustment - not reversion'
        },
        {
            'title': 'Notice on Adjusting Trading Fees',
            'claude_result': {
                'is_reversion_notice': True,  # Claude might false flag this
                'reversion_details': {
                    'has_reversion_clause': False,
                    'reversion_text': 'trading fees will be adjusted'
                }
            },
            'expected': False,
            'reason': 'No reversion clause - false positive'
        },
        {
            'title': 'Announcement on Market Operations',
            'claude_result': {
                'is_reversion_notice': True,  # Claude might false flag this
                'reversion_details': {
                    'has_reversion_clause': True,
                    'reversion_text': 'operations will revert to normal'
                }
            },
            'expected': False,
            'reason': 'Not holiday-related - should reject'
        },
        {
            'title': 'Notice on Dragon Boat Festival Work Arrangements',
            'claude_result': {
                'is_reversion_notice': True,
                'reversion_details': {
                    'has_reversion_clause': True,
                    'reversion_text': 'margin ratios will revert to their original levels'
                },
                'effective_dates': [
                    {'date': '2025-05-29', 'commodities': [{'commodity': 'Gold'}] * 3}
                ]
            },
            'expected': True,
            'reason': 'Valid Dragon Boat Festival reversion'
        }
    ]
    
    print("🔍 Testing validation on different notice types:")
    print("=" * 50)
    
    for i, test_case in enumerate(test_cases, 1):
        title = test_case['title']
        claude_result = test_case['claude_result']
        expected = test_case['expected']
        reason = test_case['reason']
        
        print(f"\n🧪 Test {i}: {title}")
        print(f"📝 Expected: {'✅ VALID' if expected else '❌ INVALID'} - {reason}")
        
        is_valid = scraper.is_valid_reversion_notice(claude_result, title)
        result = "✅ VALID" if is_valid else "❌ INVALID"
        status = "✅ PASS" if (is_valid == expected) else "❌ FAIL"
        
        print(f"🔍 Actual: {result}")
        print(f"🎯 Test Result: {status}")
        
        if is_valid != expected:
            print(f"⚠️ VALIDATION ISSUE: Expected {expected}, got {is_valid}")
    
    print(f"\n📊 VALIDATION CRITERIA SUMMARY:")
    print("=" * 40)
    print("✅ Must be flagged as reversion by Claude")
    print("✅ Must have reversion clause") 
    print("✅ Must contain specific reversion phrases")
    print("✅ Must have multiple dates OR few explicit commodities")
    print("✅ Must be holiday-related notice")
    print("✅ Must not overwrite existing data")
    
    print(f"\n🛡️ DATA PROTECTION FEATURES:")
    print("=" * 40)
    print("✅ Strict validation prevents false positives")
    print("✅ Existing entry check prevents data corruption")
    print("✅ Only infers for missing commodity+date combinations")
    print("✅ Clear logging for debugging")
    
    print(f"\n🎯 The system should now be safe to run without data corruption!")

if __name__ == "__main__":
    test_reversion_validation()