#!/usr/bin/env python3
import os
import getpass
from datetime import datetime, timedelta

# Import the main scraper class from the existing file
from shfe_scraper import LLMEnhancedSHFEScraper

def main():
    """
    A local runner script for the SHFE scraper.
    This script bypasses the Flask app and GCS upload for local testing.
    """
    print("🚀 Starting local SHFE Scraper run...")

    # --- Configuration ---

    # 1. Get the Gemini API Key
    # The script will first check for the environment variable.
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("⚠️ GEMINI_API_KEY environment variable not found.")
        try:
            # Fallback to prompting the user if the variable isn't set
            api_key = getpass.getpass("🔑 Please enter your Gemini API Key: ")
        except (IOError, EOFError):
            print("\n❌ Could not read API key. Aborting.")
            return

    if not api_key:
        print("❌ An API Key is required to run the scraper. Aborting.")
        return

    # 2. Define the Start Date for scraping
    # IMPROVED: Use a much broader date range to find margin adjustment notices
    # Margin adjustments are typically announced during:
    # - Holiday periods (Spring Festival, National Day, etc.)
    # - Market volatility periods
    # - Quarterly reviews
    
    # Option 1: Start from beginning of current year
    # start_date = f"{datetime.now().year}-01-01"
    
    # Option 2: Start from 6 months ago (more conservative)
    start_date = (datetime.now() - timedelta(days=1800)).strftime('%Y-%m-%d')
    
    # Option 3: Start from a specific known period (e.g., 2024 data)
    # start_date = "2024-01-01"
    
    print(f"📅 Using start date for scraping: {start_date}")
    print(f"💡 Tip: Margin adjustment notices are typically found during:")
    print(f"   • Holiday periods (Spring Festival, National Day)")
    print(f"   • Market volatility periods")
    print(f"   • Quarterly or monthly reviews")
    print(f"   • Try start_date='2024-01-01' for more historical data")

    # 3. Define the Local Output Directory
    # All files (CSV, XLS, ZIP) will be saved here.
    output_dir = "shfe_local_output"
    os.makedirs(output_dir, exist_ok=True)
    print(f"📂 Output will be saved to the './{output_dir}' directory.")

    # --- Scraper Execution ---
    try:
        # Initialize the scraper with our local configuration
        scraper = LLMEnhancedSHFEScraper(
            start_date=start_date,
            gemini_api_key=api_key,
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
            print(f"   📦 Output files ready for upload to cloud storage")
            print(f"   💾 CSV data file: Available in output directory")
            print(f"   📋 XLS data and metadata files: Included in ZIP")
        else:
            print("\n💡 Scraper ran, but no new data was found or no output file was generated.")
            print("\n🔍 TROUBLESHOOTING SUGGESTIONS:")
            print("   1. Try a broader date range (e.g., start from 2024-01-01)")
            print("   2. Check if margin adjustment notices exist in the date range")
            print("   3. Verify the SHFE website structure hasn't changed")
            print("   4. Look for notices with titles containing:")
            print("      • '关于调整...保证金比例...通知'")
            print("      • 'Notice on Adjusting the Margin Ratio'")

    except Exception as e:
        print(f"\n❌ An unexpected error occurred during the local run: {e}")
        import traceback
        traceback.print_exc()
        
        print(f"\n🔧 DEBUG SUGGESTIONS:")
        print("   1. Check if Chrome/ChromeDriver is properly installed")
        print("   2. Verify internet connectivity to SHFE website")
        print("   3. Ensure Gemini API key is valid and has quota")
        print("   4. Try running with a different date range")

if __name__ == "__main__":
    main()