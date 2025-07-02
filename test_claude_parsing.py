#!/usr/bin/env python3
"""
Test Claude parsing logic directly on the Labor Day notice content.
This allows quick testing of the reversion detection without browser setup.
"""
import os
import getpass
import json
from shfe_scraper import LLMEnhancedSHFEScraper

def test_claude_parsing():
    """Test Claude parsing on Labor Day notice content"""
    print("🧪 Testing Claude parsing logic on Labor Day notice...")
    
    # Get API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        try:
            api_key = getpass.getpass("🔑 Please enter your Anthropic API Key: ")
        except (IOError, EOFError):
            print("\n❌ Could not read API key. Aborting.")
            return
    
    # Sample content from the Labor Day notice (simplified for testing)
    test_title = "Notice on Work Arrangements during Labor Day 2025"
    test_content = """
    Notice on Work Arrangements during Labor Day 2025
    
    To ensure the smooth operation of the market during the Labor Day holiday period in 2025, the Shanghai Futures Exchange will adjust the margin ratios and daily price limits for various futures and options contracts.

    Starting from the closing settlement on April 29, 2025, the trading margin ratios and daily price limits for various futures and options contracts will be adjusted as follows:

    1. The price limits for rebar, hot-rolled coil and stainless steel futures contracts are adjusted to 8%, the margin ratio for hedging transactions is adjusted to 9%, and the margin ratio for speculative transactions is adjusted to 10%.

    2. The price limits for aluminum, zinc, lead, alumina, wire rod and pulp futures contracts were adjusted to 9%, the margin ratio for hedging transactions was adjusted to 10%, and the margin ratio for speculative transactions was adjusted to 11%.

    3. The price limit of copper futures contracts is adjusted to 10%, the margin ratio for hedging transactions is adjusted to 11%, and the margin ratio for speculative transactions is adjusted to 12%.

    4. The price limit of natural rubber futures contracts was adjusted to 11%, the margin ratio for hedging transactions was adjusted to 12%, and the margin ratio for speculative transactions was adjusted to 13%.

    5. The price limits for fuel oil, petroleum asphalt, butadiene rubber, nickel and tin futures contracts were adjusted to 12%, the margin ratio for hedging transactions was adjusted to 13%, and the margin ratio for speculative transactions was adjusted to 14%.

    6. The price limit of silver futures contracts is adjusted to 13%, the margin ratio for hedging transactions is adjusted to 14%, and the margin ratio for speculative transactions is adjusted to 15%.

    7. The price limit range of gold futures contracts was adjusted to 14%, the margin ratio for hedging transactions was adjusted to 15%, and the margin ratio for speculative transactions was adjusted to 16%.

    On May 6, 2025, after trading resumes, the Shanghai Futures Exchange will adjust the margin ratios and daily price limits for various futures and options contracts.

    For example, after trading on May 6, the margin ratios for gold futures will be set to:
    - Hedging margin ratio: 13%
    - Speculative margin ratio: 14%
    The daily price limit will be adjusted to 12%.

    For other contracts, the daily price limits and margin ratios will revert to their original levels unless otherwise specified.

    All futures and options contracts will undergo a call auction from 08:55 to 09:00 on May 6, and night trading will resume that evening.
    """
    
    try:
        # Initialize scraper to access Claude parser
        scraper = LLMEnhancedSHFEScraper(
            start_date='2025-04-01',
            anthropic_api_key=api_key,
            output_dir='test_output'
        )
        parser = scraper.claude_parser
        
        print("🤖 Parsing content with enhanced Claude logic...")
        result = parser.parse_margin_notice(test_content, test_title)
        
        print("\n📊 Parsing Results:")
        print(f"   🔍 Is margin notice: {result.get('is_margin_notice', False)}")
        print(f"   🔄 Is reversion notice: {result.get('is_reversion_notice', False)}")
        print(f"   📅 Effective dates found: {len(result.get('effective_dates', []))}")
        print(f"   💾 Total entries: {result.get('total_entries', 0)}")
        print(f"   📈 Total commodities: {result.get('total_commodities', 0)}")
        print(f"   🎯 Confidence: {result.get('parsing_confidence', 'unknown')}")
        
        # Show reversion details
        reversion_details = result.get('reversion_details', {})
        if reversion_details:
            print(f"\n🔄 Reversion Details:")
            print(f"   📝 Has explicit commodities: {reversion_details.get('has_explicit_commodities', False)}")
            print(f"   🔄 Has reversion clause: {reversion_details.get('has_reversion_clause', False)}")
            print(f"   📄 Reversion text: {reversion_details.get('reversion_text', 'N/A')}")
        
        # Show effective dates and commodities
        for i, date_entry in enumerate(result.get('effective_dates', [])):
            effective_date = date_entry.get('date', 'Unknown')
            commodities = date_entry.get('commodities', [])
            print(f"\n📅 Date {i+1}: {effective_date}")
            print(f"   💼 Commodities: {len(commodities)}")
            
            for j, commodity in enumerate(commodities[:3]):  # Show first 3
                name = commodity.get('commodity', 'Unknown')
                hedging = commodity.get('hedging_percentage', 'N/A')
                speculative = commodity.get('speculative_percentage', 'N/A')
                adj_type = commodity.get('adjustment_type', 'N/A')
                print(f"   📊 {name}: {hedging}%/{speculative}% [{adj_type}]")
            
            if len(commodities) > 3:
                print(f"   ... and {len(commodities) - 3} more")
        
        # Show excluded items
        excluded = result.get('excluded_non_commodities', [])
        if excluded:
            print(f"\n🚫 Excluded non-commodities: {excluded}")
        
        # Show raw JSON for debugging
        print(f"\n🔧 Raw JSON Result:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Test key expectations
        print(f"\n✅ Test Validation:")
        expected_april_29 = any(d.get('date') == '2025-04-29' for d in result.get('effective_dates', []))
        expected_may_6 = any(d.get('date') == '2025-05-06' for d in result.get('effective_dates', []))
        
        print(f"   📅 April 29 date detected: {'✅' if expected_april_29 else '❌'}")
        print(f"   📅 May 6 date detected: {'✅' if expected_may_6 else '❌'}")
        print(f"   🔄 Reversion notice detected: {'✅' if result.get('is_reversion_notice') else '❌'}")
        
        if expected_april_29 and expected_may_6 and result.get('is_reversion_notice'):
            print(f"\n🎉 SUCCESS: Claude correctly identified reversion pattern!")
        else:
            print(f"\n⚠️ NEEDS TUNING: Some expected patterns not detected")
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_claude_parsing()