#!/usr/bin/env python3
"""
Test script to process a specific SHFE notice and test the reversion logic.
This helps validate the enhanced Claude parsing and inference system.
"""
import os
import getpass
from datetime import datetime, date
from shfe_scraper import LLMEnhancedSHFEScraper

def test_specific_notice():
    """Test the Labor Day notice with reversion logic"""
    print("🧪 Testing specific SHFE notice with reversion logic...")
    
    # Get API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        try:
            api_key = getpass.getpass("🔑 Please enter your Anthropic API Key: ")
        except (IOError, EOFError):
            print("\n❌ Could not read API key. Aborting.")
            return
    
    if not api_key:
        print("❌ API Key required for testing.")
        return
    
    # Test notice URL - Labor Day notice with reversion clause
    test_url = "https://www.shfe.com.cn/publicnotice/notice/202504/t20250425_827640.html"
    test_title = "Notice on Work Arrangements during Labor Day 2025"
    test_date = date(2025, 4, 25)
    
    # Create output directory for test
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"🎯 Testing notice: {test_title}")
    print(f"📄 URL: {test_url}")
    print(f"📅 Notice date: {test_date}")
    
    try:
        # Initialize scraper
        scraper = LLMEnhancedSHFEScraper(
            start_date='2025-04-01',
            anthropic_api_key=api_key,
            output_dir=output_dir
        )
        
        # Set up minimal environment for testing
        scraper.setup_driver()
        scraper.setup_csv()
        
        print("\n🤖 Processing notice with enhanced Claude logic...")
        
        # Test the specific notice processing
        margin_count = scraper.scrape_notice_content(test_url, test_title, test_date)
        
        print(f"\n📊 Initial extraction results:")
        print(f"   💾 Direct entries extracted: {margin_count}")
        
        # Check if reversion notices were detected
        if hasattr(scraper, 'reversion_notices') and scraper.reversion_notices:
            print(f"   🔄 Reversion notices detected: {len(scraper.reversion_notices)}")
            
            # Process reversion logic
            print("\n🔄 Testing reversion inference logic...")
            reversion_count = scraper.process_reversion_notices()
            print(f"   💾 Inferred entries: {reversion_count}")
            
        else:
            print("   ⚠️ No reversion notices detected")
        
        # Show results summary
        print(f"\n📈 Test Results Summary:")
        print(f"   📄 Total entries in dataset: {len(scraper.extracted_data)}")
        
        # Show entries by effective date
        dates_summary = {}
        for entry in scraper.extracted_data:
            eff_date = entry['effective_date']
            if eff_date not in dates_summary:
                dates_summary[eff_date] = []
            dates_summary[eff_date].append(entry['commodity'])
        
        for eff_date in sorted(dates_summary.keys()):
            commodities = dates_summary[eff_date]
            print(f"   📅 {eff_date}: {len(commodities)} commodities ({', '.join(commodities[:5])}{'...' if len(commodities) > 5 else ''})")
        
        # Check specifically for May 6 entries (the key test)
        may_6_entries = [e for e in scraper.extracted_data if e['effective_date'] == '2025-05-06']
        print(f"\n🎯 May 6, 2025 entries (key reversion test): {len(may_6_entries)}")
        
        if may_6_entries:
            print("   ✅ May 6 reversion logic working!")
            for entry in may_6_entries[:5]:  # Show first 5
                method = entry['parsing_method']
                print(f"   📊 {entry['commodity']}: {entry['hedging_percentage']}%/{entry['speculative_percentage']}% [{method}]")
            if len(may_6_entries) > 5:
                print(f"   ... and {len(may_6_entries) - 5} more")
        else:
            print("   ❌ May 6 entries missing - reversion logic may need adjustment")
        
        # Show the test CSV file
        print(f"\n📁 Test results saved to: {output_dir}/shfe_margin_ratios_llm_{datetime.now().strftime('%Y%m%d')}.csv")
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if hasattr(scraper, 'driver') and scraper.driver:
            scraper.driver.quit()

if __name__ == "__main__":
    test_specific_notice()