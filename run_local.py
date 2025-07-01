#!/usr/bin/env python3
import os
import getpass
from datetime import datetime, timedelta

# Import the main scraper class from the existing file
# This file (shfe_scraper.py) should contain the Anthropic-based scraper
from shfe_scraper import LLMEnhancedSHFEScraper

def main():
    """
    A local runner script for the SHFE scraper.
    This script bypasses the Flask app and GCS upload for local testing.
    """
    print("🚀 Starting local SHFE Scraper run...")

    # --- Configuration ---

    # 1. Get the Anthropic API Key
    # The script will first check for the environment variable.
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY environment variable not found.")
        try:
            # Fallback to prompting the user if the variable isn't set
            api_key = getpass.getpass("🔑 Please enter your Anthropic API Key: ")
        except (IOError, EOFError):
            print("\n❌ Could not read API key. Aborting.")
            return

    if not api_key:
        print("❌ An API Key is required to run the scraper. Aborting.")
        return

    # 2. Define the Start Date for scraping
    # Using a broad date range to find margin adjustment notices, which are
    # typically announced during holiday periods or market volatility.
    
    # Start from 5 years ago to ensure a wide search window
    # start_date = (datetime.now() - timedelta(days=1825)).strftime('%Y-%m-%d')
    start_date = '2025-05-05'  # Expanded to capture more margin adjustments
    print(f"📅 Using start date for scraping: {start_date}")
    print(f"💡 Tip: Margin adjustment notices are typically found during:")
    print(f"   • Holiday periods (Spring Festival, National Day)")
    print(f"   • Market volatility periods")
    print(f"   • Quarterly or monthly reviews")

    # 3. Define the Local Output Directory
    # All files (CSV, XLS, ZIP) will be saved here.
    output_dir = "shfe_local_output"
    os.makedirs(output_dir, exist_ok=True)
    print(f"📂 Output will be saved to the './{output_dir}' directory.")

    # --- Scraper Execution ---
    try:
        # Initialize the scraper with our local configuration for Anthropic
        scraper = LLMEnhancedSHFEScraper(
            start_date=start_date,
            anthropic_api_key=api_key,
            output_dir=output_dir
        )

        # Execute the main scraper method
        zip_file_path = scraper.run_scraper()

        if zip_file_path and os.path.exists(zip_file_path):
            print("\n✅ Local run completed successfully!")
            print(f"📦 Final output ZIP file located at: {zip_file_path}")
            
            # Additional success info
            print(f"\n📊 SUCCESS SUMMARY:")
            print(f"   📅 Date range searched: {start_date} to {datetime.now().strftime('%Y-%m-%d')}")
            print(f"   🤖 LLM Used: Anthropic (Claude)")
            print(f"   💾 CSV data file: Available in the output directory")
            print(f"   📋 XLS data and metadata files: Included in the ZIP archive")
        else:
            print("\n💡 Scraper ran, but no new data was found or no output file was generated.")
            print("\n🔍 TROUBLESHOOTING SUGGESTIONS:")
            print("   1. Try a different or broader date range.")
            print("   2. Check if margin adjustment notices actually exist in the searched date range on the SHFE website.")
            print("   3. Verify the SHFE website structure hasn't changed, preventing the scraper from finding notices.")
            print("   4. Look for notices with titles containing:")
            print("      • '关于调整...保证金比例...通知'")
            print("      • 'Notice on Adjusting the Margin Ratio'")

    except Exception as e:
        print(f"\n❌ An unexpected error occurred during the local run: {e}")
        import traceback
        traceback.print_exc()
        
        print(f"\n🔧 DEBUG SUGGESTIONS:")
        print("   1. Check if Chrome/ChromeDriver is properly installed and in your PATH.")
        print("   2. Verify your internet connection to the SHFE website.")
        print("   3. Ensure your Anthropic API key is valid and has sufficient quota.")
        print("   4. Make sure the 'anthropic' library is installed (`pip install anthropic`).")

if __name__ == "__main__":
    main()