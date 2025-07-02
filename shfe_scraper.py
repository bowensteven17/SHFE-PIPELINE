#!/usr/bin/env python3
"""
LLM-Enhanced SHFE Margin Scraper
Uses your working scraper + Claude for intelligent content parsing
Enhanced with improved parsing logic from txt file for near 100% accuracy
"""

import time
import csv
import re
import os
import json
import xlwt
import zipfile
from datetime import datetime, date
from typing import List, Optional, Dict, Tuple
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, InvalidSessionIdException, NoSuchElementException
from datetime import timedelta

# Claude integration
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    print("⚠️ Anthropic not installed. Run: pip install anthropic")
    ANTHROPIC_AVAILABLE = False

# ==================== CONFIGURATION (now passed via __init__) ====================
# START_DATE = "2025-01-10"
# DATASET_NAME = "SHFEMR"
# OUTPUT_DIR = "shfe_output"
# ANTHROPIC_API_KEY = "..."
# =================================================================================

class SHFEDataExporter:
    """Export data in runbook format"""
    
    def __init__(self, dataset_name: str, output_dir: str):
        self.dataset_name = dataset_name
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def create_xls_files(self, data_entries: List[Dict], release_date: str) -> Tuple[str, str]:
        """Create DATA and META XLS files according to runbook"""
        timestamp = datetime.now().strftime("%Y%m%d")
        
        data_filename = f"{self.dataset_name}_DATA_{timestamp}.xls"
        meta_filename = f"{self.dataset_name}_META_{timestamp}.xls"
        
        data_path = os.path.join(self.output_dir, data_filename)
        meta_path = os.path.join(self.output_dir, meta_filename)
        
        self._create_data_file(data_entries, data_path)
        self._create_meta_file(meta_path, release_date)
        
        return data_path, meta_path
    
    def _create_data_file(self, data_entries: List[Dict], filepath: str):
        """Create DATA XLS file"""
        workbook = xlwt.Workbook(encoding='utf-8')
        worksheet = workbook.add_sheet('Data')
        
        # Commodity name mapping to match example format
        commodity_mapping = {
            'COPPER': 'COPPER',
            'ALUMINUM': 'ALUMINIUM',
            'ZINC': 'ZINC',
            'LEAD': 'LEAD',
            'NICKEL': 'NICKEL',
            'TIN': 'TIN',
            'ALUMINA': 'ALUMINA',
            'GOLD': 'GOLD',
            'SILVER': 'SILVER',
            'REBAR': 'REBAR',
            'HOT_ROLLED_COIL': 'HOTROLLCOIL',
            'HOT-ROLLED_COIL': 'HOTROLLCOIL',
            'STAINLESS_STEEL': 'STAINLESSSTEEL',
            'NATURAL_RUBBER': 'NATURRUBBER',
            'FUEL_OIL': 'FUELOIL',
            'PETROLEUM_ASPHALT': 'PETASPHALT',
            'WIRE_ROD': 'WIREROD',
            'BUTADIENE_RUBBER': 'BUTRUBBER',
            'PULP': 'PULP'
        }
        
        # Description mapping for commodities
        commodity_descriptions = {
            'COPPER': 'Copper',
            'ALUMINIUM': 'Aluminium',
            'ZINC': 'Zinc',
            'LEAD': 'Lead',
            'NICKEL': 'Nickel',
            'TIN': 'Tin',
            'ALUMINA': 'Alumina',
            'GOLD': 'Gold',
            'SILVER': 'Silver',
            'REBAR': 'Rebar',
            'HOTROLLCOIL': 'Hot-rolled Coil',
            'STAINLESSSTEEL': 'Stainless Steel',
            'NATURRUBBER': 'Natural Rubber',
            'FUELOIL': 'Fuel Oil',
            'PETASPHALT': 'Petroleum Asphalt ',
            'WIREROD': 'Wire Rod',
            'BUTRUBBER': 'Butadiene Rubber',
            'PULP': 'Pulp'
        }
        
        # Group data by effective date
        data_by_date = {}
        time_series_codes = set()
        
        for entry in data_entries:
            effective_date = entry['effective_date']
            commodity_raw = entry['commodity'].upper().replace(' ', '_').replace('-', '_')
            
            # Map commodity name to expected format
            commodity = commodity_mapping.get(commodity_raw, commodity_raw)
            
            if effective_date not in data_by_date:
                data_by_date[effective_date] = {}
            
            hedging_code = f"SHFEMR.{commodity}.HEDGERS.B"
            speculative_code = f"SHFEMR.{commodity}.SPECULATORS.B"
            
            data_by_date[effective_date][hedging_code] = entry['hedging_percentage']
            data_by_date[effective_date][speculative_code] = entry['speculative_percentage']
            
            time_series_codes.add(hedging_code)
            time_series_codes.add(speculative_code)
        
        # Define exact column order to match example file
        column_order = [
            'COPPER', 'ALUMINA', 'LEAD', 'ZINC', 'ALUMINIUM', 'GOLD', 'NICKEL', 'REBAR', 
            'PULP', 'NATURRUBBER', 'SILVER', 'FUELOIL', 'PETASPHALT', 'WIREROD', 'TIN', 
            'BUTRUBBER', 'HOTROLLCOIL', 'STAINLESSSTEEL'
        ]
        
        # Create ordered list of codes
        ordered_codes = []
        for commodity in column_order:
            hedging_code = f"SHFEMR.{commodity}.HEDGERS.B"
            speculative_code = f"SHFEMR.{commodity}.SPECULATORS.B"
            # Only add codes that exist in our data
            if hedging_code in time_series_codes:
                ordered_codes.append(hedging_code)
            if speculative_code in time_series_codes:
                ordered_codes.append(speculative_code)
        
        # Write headers - first row is empty, second row has column headers
        worksheet.write(0, 0, "")
        worksheet.write(1, 0, "")
        
        for col_idx, code in enumerate(ordered_codes, 1):
            worksheet.write(0, col_idx, code)
            # Extract commodity name from code for description
            commodity_code = code.split('.')[1]
            commodity_desc = commodity_descriptions.get(commodity_code, commodity_code.replace('_', ' ').title())
            transaction_type = "hedging" if "HEDGERS" in code else "speculative"
            description = f"{commodity_desc}: Margin ratio for {transaction_type} transactions"
            worksheet.write(1, col_idx, description)
        
        # Write data
        sorted_dates = sorted(data_by_date.keys())
        for row_idx, effective_date in enumerate(sorted_dates, 2):
            worksheet.write(row_idx, 0, effective_date)
            
            for col_idx, code in enumerate(ordered_codes, 1):
                value = data_by_date[effective_date].get(code, "")
                worksheet.write(row_idx, col_idx, value)
        
        workbook.save(filepath)
        print(f"✅ Created DATA file: {filepath}")
    
    def _create_meta_file(self, filepath: str, release_date: str):
        """Create META XLS file"""
        workbook = xlwt.Workbook(encoding='utf-8')
        worksheet = workbook.add_sheet('Metadata')
        
        headers = [
            'TIMESERIES_ID', 'TIMESERIES_DESCRIPTION', 'UNIT', 'FREQUENCY',
            'SOURCE', 'DATASET', 'LAST_RELEASE_DATE', 'NEXT_RELEASE_DATE'
        ]
        
        for col_idx, header in enumerate(headers):
            worksheet.write(0, col_idx, header)
        
        # Sample metadata for common commodities (using same mapping as DATA file)
        commodity_mapping = {
            'COPPER': 'COPPER',
            'ALUMINUM': 'ALUMINIUM',
            'ZINC': 'ZINC',
            'LEAD': 'LEAD',
            'NICKEL': 'NICKEL',
            'TIN': 'TIN',
            'ALUMINA': 'ALUMINA',
            'GOLD': 'GOLD',
            'SILVER': 'SILVER',
            'REBAR': 'REBAR',
            'HOT_ROLLED_COIL': 'HOTROLLCOIL',
            'STAINLESS_STEEL': 'STAINLESSSTEEL',
            'NATURAL_RUBBER': 'NATURRUBBER',
            'FUEL_OIL': 'FUELOIL',
            'PETROLEUM_ASPHALT': 'PETASPHALT',
            'WIRE_ROD': 'WIREROD',
            'BUTADIENE_RUBBER': 'BUTRUBBER',
            'PULP': 'PULP'
        }
        
        commodity_descriptions = {
            'COPPER': 'Copper',
            'ALUMINIUM': 'Aluminium',
            'ZINC': 'Zinc',
            'LEAD': 'Lead',
            'NICKEL': 'Nickel',
            'TIN': 'Tin',
            'ALUMINA': 'Alumina',
            'GOLD': 'Gold',
            'SILVER': 'Silver',
            'REBAR': 'Rebar',
            'HOTROLLCOIL': 'Hot-rolled Coil',
            'STAINLESSSTEEL': 'Stainless Steel',
            'NATURRUBBER': 'Natural Rubber',
            'FUELOIL': 'Fuel Oil',
            'PETASPHALT': 'Petroleum Asphalt',
            'WIREROD': 'Wire Rod',
            'BUTRUBBER': 'Butadiene Rubber',
            'PULP': 'Pulp'
        }
        
        commodities = list(commodity_mapping.values())
        transaction_types = [('HEDGERS', 'hedging'), ('SPECULATORS', 'speculative')]
        
        row_idx = 1
        for commodity in commodities:
            for transaction_type, transaction_desc in transaction_types:
                timeseries_id = f"SHFEMR.{commodity}.{transaction_type}.B"
                commodity_desc = commodity_descriptions.get(commodity, commodity.replace('_', ' ').title())
                description = f"{commodity_desc}: Margin ratio for {transaction_desc} transactions"
                
                worksheet.write(row_idx, 0, timeseries_id)
                worksheet.write(row_idx, 1, description)
                worksheet.write(row_idx, 2, "Percentage")
                worksheet.write(row_idx, 3, "Weekdaily")
                worksheet.write(row_idx, 4, "Shanghai Futures Exchange")
                worksheet.write(row_idx, 5, self.dataset_name)
                worksheet.write(row_idx, 6, f"{release_date}T11:00:00")
                worksheet.write(row_idx, 7, "")
                
                row_idx += 1
        
        workbook.save(filepath)
        print(f"✅ Created META file: {filepath}")
    
    def create_zip_archive(self, data_path: str, meta_path: str) -> str:
        """Create ZIP archive"""
        timestamp = datetime.now().strftime("%Y%m%d")
        zip_filename = f"{self.dataset_name}_{timestamp}.ZIP"
        zip_path = os.path.join(self.output_dir, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(data_path, os.path.basename(data_path))
            zipf.write(meta_path, os.path.basename(meta_path))
        
        print(f"📦 Created ZIP archive: {zip_path}")
        return zip_path

class ClaudeContentParser:
    """Claude-powered intelligent content parsing for SHFE notices with enhanced logic"""
    
    def __init__(self, api_key: str):
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("Anthropic library not available")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        
    def parse_margin_notice(self, notice_content: str, notice_title: str) -> Dict:
        """Use Claude to intelligently parse margin ratio notices with enhanced logic from txt file"""
        
        prompt = f"""You are an expert at parsing Shanghai Futures Exchange (SHFE) and Shanghai International Energy Exchange margin ratio notices. Your job is to extract ALL margin ratio data with PERFECT accuracy using the enhanced parsing logic.

NOTICE TITLE: {notice_title}

NOTICE CONTENT: {notice_content}

ENHANCED PARSING RULES (from txt file analysis):

1. EFFECTIVE DATE IDENTIFICATION PATTERNS:
   - PRIMARY: "trading margin ratio and price limit range will be adjusted as follows" 
   - SECONDARY: "trading margin ratio will be adjusted as follows"
   - The date is usually mentioned BEFORE these phrases in the same sentence
   - Look for: "Starting from the closing settlement on [DATE]" or "from the closing settlement on [DATE]"
   - Look for: "After trading on [DATE], starting from the closing settlement of the first trading day"

2. COMMODITY FILTERING:
   - INCLUDE ONLY physical commodities: copper, aluminum, zinc, lead, nickel, tin, alumina, gold, silver, rebar, hot-rolled coil, wire rod, stainless steel, fuel oil, petroleum asphalt, butadiene rubber, natural rubber, pulp, crude oil, low-sulfur fuel oil, No. 20 rubber, international copper
   - EXCLUDE financial indices: container shipping index, freight rates, any "index" contracts
   - EXCLUDE non-commodity contracts

3. MULTIPLE COMMODITIES IN ONE SENTENCE:
   - When sentence mentions "aluminum, zinc, lead, alumina, wire rod and pulp futures contracts were adjusted to 9%, margin ratio for hedging transactions was adjusted to 10%, and speculative transactions to 11%"
   - Extract as SEPARATE entries:
     * commodity=(aluminum) Hedging_Percentage=(10) Speculative_Percentage=(11)
     * commodity=(zinc) Hedging_Percentage=(10) Speculative_Percentage=(11)
     * commodity=(lead) Hedging_Percentage=(10) Speculative_Percentage=(11)
     * commodity=(alumina) Hedging_Percentage=(10) Speculative_Percentage=(11)
     * commodity=(wire rod) Hedging_Percentage=(10) Speculative_Percentage=(11)
     * commodity=(pulp) Hedging_Percentage=(10) Speculative_Percentage=(11)

4. HANDLING SPECIAL STATEMENTS:
   - "remains at X%" → Extract the actual percentage value, mark as "remains_at"
   - "restored to their original levels" → Mark as "restored_to_original" and note previous lookup needed
   - "revert to original levels" → Mark as "reverted_to_original" 
   - "恢复原水平" / "恢复到原来水平" → Mark as "reverted_to_original"
   - "unless otherwise specified" → Indicates reversion for unlisted commodities
   - ALWAYS extract the margin ratios (hedging/speculative), NOT price limits

5. REVERSION NOTICE DETECTION:
   - Look for phrases like "will revert to their original levels", "unless otherwise specified"
   - If notice mentions specific commodities with new ratios AND says others revert, mark this as a reversion notice
   - For reversion notices, extract BOTH explicit ratios AND identify which commodities should revert
   - Example: "Gold futures will be adjusted to 13%/14%. All other contracts will revert to original levels."
     Should extract: Gold with explicit ratios + reversion_notice=true for inference processing

6. VALIDATION RULES:
   - All margin percentages must be ≤ 20%
   - If percentage > 20%, exclude that commodity (likely not a physical commodity)
   - Hedging percentage should be ≤ Speculative percentage (usually)

7. COMMODITY NAME STANDARDIZATION:
   - 铜/copper/international copper → "Copper"
   - 铝/aluminum → "Aluminum" 
   - 锌/zinc → "Zinc"
   - 铅/lead → "Lead"
   - 镍/nickel → "Nickel"
   - 锡/tin → "Tin"
   - 氧化铝/alumina → "Alumina"
   - 黄金/gold → "Gold"
   - 白银/silver → "Silver"
   - 螺纹钢/rebar → "Rebar"
   - 热轧卷板/hot-rolled coil → "Hot-rolled Coil"
   - 线材/wire rod → "Wire Rod"
   - 不锈钢/stainless steel → "Stainless Steel"
   - 燃料油/fuel oil → "Fuel Oil"
   - 石油沥青/petroleum asphalt → "Petroleum Asphalt"
   - 丁二烯橡胶/butadiene rubber → "Butadiene Rubber"
   - 天然橡胶/natural rubber/No. 20 rubber → "Natural Rubber"
   - 纸浆/pulp → "Pulp"
   - 原油/crude oil → "Crude Oil"
   - 低硫燃料油/low-sulfur fuel oil → "Low-sulfur Fuel Oil"

EXAMPLES FROM TXT FILE:

Example 1 - Multiple commodities:
"The price limits for aluminum, zinc, lead, alumina, wire rod and pulp futures contracts were adjusted to 9%, the margin ratio for hedging transactions was adjusted to 10%, and the margin ratio for speculative transactions was adjusted to 11%"

Extract as 6 separate entries, each with hedging=10%, speculative=11%

Example 2 - Single commodity:
"The price limit of copper futures contracts is adjusted to 10%, the margin ratio for hedging transactions is adjusted to 11%, and the margin ratio for speculative transactions is adjusted to 12%"

Extract as: commodity=(Copper) Hedging_Percentage=(11) Speculative_Percentage=(12)

Example 3 - Restored to original:
"The price limits and trading margin ratios of gold futures contracts will be restored to their original levels"

Extract as: commodity=(Gold) with adjustment_type="restored_to_original"

OUTPUT FORMAT (JSON only):
{{
    "is_margin_notice": true/false,
    "is_reversion_notice": true/false,
    "reversion_details": {{
        "has_explicit_commodities": true/false,
        "has_reversion_clause": true/false,
        "reversion_text": "exact text indicating reversion"
    }},
    "effective_dates": [
        {{
            "date": "YYYY-MM-DD",
            "date_source": "exact text showing this date",
            "commodities": [
                {{
                    "commodity": "standardized name",
                    "hedging_percentage": number,
                    "speculative_percentage": number,
                    "adjustment_type": "adjusted_to/remains_at/restored_to_original/reverted_to_original",
                    "source_sentence": "exact sentence with this data"
                }}
            ]
        }}
    ],
    "total_commodities": number,
    "total_entries": number,
    "parsing_confidence": "high/medium/low",
    "excluded_non_commodities": ["list of excluded items like indices"],
    "summary": "brief description of what was extracted"
}}

CRITICAL REQUIREMENTS:
- Return ONLY valid JSON
- Extract margin ratios, NOT price limits
- Duplicate data for multiple commodities in same sentence
- Validate percentages ≤ 20%
- Exclude financial indices and non-physical commodities
- Use exact date patterns from txt file logic
"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )
            
            result_text = response.content[0].text.strip()
            
            # Extract JSON
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
            else:
                json_text = result_text
            
            result = json.loads(json_text)
            
            # Enhanced logging with validation
            if result.get('is_margin_notice', False):
                total_entries = result.get('total_entries', 0)
                total_commodities = result.get('total_commodities', 0)
                total_dates = len(result.get('effective_dates', []))
                excluded_items = result.get('excluded_non_commodities', [])
                
                print(f"🤖 Claude Enhanced: Found {total_entries} entries for {total_commodities} commodities across {total_dates} dates")
                
                if excluded_items:
                    print(f"🚫 Excluded non-commodities: {excluded_items}")
                
                # Log each effective date with validation
                for date_entry in result.get('effective_dates', []):
                    date = date_entry.get('date')
                    commodities = date_entry.get('commodities', [])
                    commodity_count = len(commodities)
                    
                    # Validate percentages
                    invalid_percentages = []
                    for commodity in commodities:
                        hedging = commodity.get('hedging_percentage', 0)
                        speculative = commodity.get('speculative_percentage', 0)
                        # Handle None values from Claude parsing
                        if hedging is None:
                            hedging = 0
                        if speculative is None:
                            speculative = 0
                        if hedging > 20 or speculative > 20:
                            invalid_percentages.append(f"{commodity.get('commodity')}({hedging}%/{speculative}%)")
                    
                    print(f"📅 {date}: {commodity_count} commodities")
                    if invalid_percentages:
                        print(f"⚠️ Validation warnings for {date}: {invalid_percentages}")
            else:
                print(f"🤖 Claude Enhanced: Not a margin ratio adjustment notice")
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"❌ Claude JSON parsing error: {e}")
            print(f"Raw response: {result_text[:300]}...")
            return {"is_margin_notice": False, "effective_dates": [], "parsing_confidence": "low"}
            
        except Exception as e:
            print(f"❌ Claude parsing failed: {e}")
            return {"is_margin_notice": False, "effective_dates": [], "parsing_confidence": "low"}

class SHFECommodityExtractor:
    """Keep your existing commodity patterns with enhanced filtering"""
    
    def __init__(self):
        self.commodity_patterns = {
            'Copper': ['copper', '铜', 'cu', 'copper futures', 'copper contracts', 'international copper'],
            'Alumina': ['alumina', '氧化铝', 'aluminum oxide', 'alumina futures'],
            'Lead': ['lead', '铅', 'pb', 'lead futures', 'lead contracts'],
            'Zinc': ['zinc', '锌', 'zn', 'zinc futures', 'zinc contracts'],
            'Aluminum': ['aluminum', 'aluminium', '铝', 'al', 'aluminum futures'],
            'Gold': ['gold', '黄金', '金', 'au', 'gold futures', 'gold contracts'],
            'Nickel': ['nickel', '镍', 'ni', 'nickel futures', 'nickel contracts'],
            'Rebar': ['rebar', '螺纹钢', 'reinforcing bar', 'steel rebar'],
            'Pulp': ['pulp', '纸浆', 'wood pulp', 'bleached kraft pulp'],
            'Natural Rubber': ['natural rubber', 'rubber', '天然橡胶', '橡胶', 'nr', 'No. 20 rubber'],
            'Silver': ['silver', '白银', '银', 'ag', 'silver futures'],
            'Fuel Oil': ['fuel oil', '燃料油', 'marine fuel', 'bunker fuel'],
            'Petroleum Asphalt': ['petroleum asphalt', 'asphalt', '石油沥青', '沥青'],
            'Wire Rod': ['wire rod', '线材', 'steel wire rod'],
            'Tin': ['tin', '锡', 'sn', 'tin futures', 'tin contracts'],
            'Butadiene Rubber': ['butadiene rubber', '丁二烯橡胶', 'br'],
            'Hot-rolled Coil': ['hot-rolled coil', 'hot rolled coil', '热轧卷板', 'hrc'],
            'Stainless Steel': ['stainless steel', '不锈钢', 'ss'],
            'Crude Oil': ['crude oil', '原油', 'crude', 'oil futures'],
            'Low-sulfur Fuel Oil': ['low-sulfur fuel oil', 'low sulfur fuel oil', '低硫燃料油']
        }
        
        # Non-commodity patterns to exclude
        self.excluded_patterns = [
            'container shipping index', 'freight', 'index', 'shipping', 'csi',
            'financial index', 'stock index', 'bond', 'currency'
        ]

class LLMEnhancedSHFEScraper:
    """Your working scraper enhanced with Claude content parsing and improved logic"""
    
    def __init__(self, start_date: str, anthropic_api_key: str, output_dir: str):
        self.start_date_str = start_date
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        self.today = date.today()
        self.base_url = "https://www.shfe.com.cn/publicnotice/notice/"
        self.driver = None
        self.wait = None
        
        # New: Parameterized config
        self.output_dir = output_dir
        self.dataset_name = "SHFEMR"
        self.csv_output = os.path.join(self.output_dir, f"shfe_margin_ratios_llm_{datetime.now().strftime('%Y%m%d')}.csv")

        
        # Initialize components
        self.data_exporter = SHFEDataExporter(self.dataset_name, self.output_dir)
        self.commodity_extractor = SHFECommodityExtractor()
        self.extracted_data = []
        
        # Initialize Claude parser
        if anthropic_api_key:
            try:
                self.claude_parser = ClaudeContentParser(anthropic_api_key)
                print("🤖 Claude content parser initialized with enhanced logic")
            except Exception as e:
                print(f"⚠️ Claude initialization failed: {e}")
                self.claude_parser = None
        else:
            print("⚠️ Anthropic API key not provided. Claude parsing will be disabled.")
            self.claude_parser = None
        
    def setup_driver(self):
        """Initialize Chrome driver with robust timeout and performance settings"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-tools")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-ipc-flooding-protection")
        # Performance optimizations
        chrome_options.add_argument("--disable-images")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-background-networking")
        chrome_options.add_argument("--aggressive-cache-discard")
        # Translation settings
        chrome_options.add_experimental_option("prefs", {
            "translate_whitelists": {"zh-CN": "en"},
            "translate": {"enabled": True}
        })
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            # More aggressive timeouts
            self.driver.set_page_load_timeout(20)  # Reduced from 30
            self.driver.implicitly_wait(5)
            self.wait = WebDriverWait(self.driver, 10)  # Reduced from 15
            print("✅ Chrome driver initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize Chrome driver: {e}")
            raise
    
    def is_driver_valid(self) -> bool:
        """Check if the WebDriver session is still valid"""
        try:
            # Simple operation to test driver validity
            self.driver.current_url
            return True
        except Exception:
            return False
    
    def restart_driver_if_needed(self, reload_page: bool = True) -> bool:
        """Restart the driver if the session is invalid. Returns True if restart was successful."""
        if not hasattr(self, 'driver') or not self.driver or not self.is_driver_valid():
            print("🔄 Driver session invalid, attempting to restart...")
            try:
                # Clean up existing driver
                if hasattr(self, 'driver') and self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                
                # Reinitialize driver
                self.setup_driver()
                
                # Reload the main page if requested
                if reload_page and hasattr(self, 'base_url'):
                    try:
                        print("🔄 Reloading main page after driver restart...")
                        self.driver.get(self.base_url)
                        time.sleep(3)  # Give time for page to load
                    except Exception as e:
                        print(f"⚠️ Failed to reload main page: {e}")
                
                print("✅ Driver restarted successfully")
                return True
            except Exception as e:
                print(f"❌ Failed to restart driver: {e}")
                return False
        return True
        
    def setup_csv(self):
        """Initialize CSV file"""
        os.makedirs(self.output_dir, exist_ok=True)
        
        if not os.path.exists(self.csv_output):
            with open(self.csv_output, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow([
                    'Date', 'Title', 'URL', 'Commodity', 'Hedging_Percentage', 
                    'Speculative_Percentage', 'Effective_Date', 'Adjustment_Type',
                    'Source_Sentence', 'Parsing_Method', 'Confidence', 'Scraped_At'
                ])
    
    def is_likely_margin_notice(self, title: str) -> bool:
        """Enhanced pre-filter notices with better margin detection"""
        strong_indicators = [
            "保证金比例", "交易保证金", "margin ratio", "price limit",
            "端午节", "劳动节", "春节", "国庆节", "中秋节",  # Holiday adjustments
            "Dragon Boat", "Labor Day", "Spring Festival", "National Day",
            "调整交易保证金", "铸造铝合金", "阴极铜", "氧化铝",  # Added specific indicators
            "工作安排", "节假日", "holiday"  # Work arrangements and holiday keywords
        ]
        weak_indicators = [
            "保证金", "限额", "调整", "margin", "ratio", "limit",
            "节假日", "holiday", "festival", "通知", "notice"
        ]
        title_lower = title.lower()
        if any(indicator in title_lower or indicator in title for indicator in strong_indicators):
            print(f"🎯 Strong margin indicator found in title: {title}")
            return True
        weak_matches = sum(1 for indicator in weak_indicators if indicator in title_lower or indicator in title)
        if weak_matches >= 2:
            print(f"🎯 Multiple weak indicators ({weak_matches}) found in title: {title}")
            return True
        print(f"⏭️ No sufficient margin indicators in title: {title}")
        return False
    
    def extract_clean_text(self, page_source: str) -> str:
        """Extract clean text from page source"""
        clean_content = re.sub(r'<script.*?</script>', '', page_source, flags=re.DOTALL)
        clean_content = re.sub(r'<style.*?</style>', '', clean_content, flags=re.DOTALL)
        clean_content = re.sub(r'<[^>]+>', ' ', clean_content)
        clean_content = re.sub(r'\s+', ' ', clean_content)
        return clean_content.strip()
    
    def scrape_notice_content(self, notice_url: str, title: str, notice_date: date) -> int:
        """Enhanced notice scraping with Claude parsing and better error handling"""
        # Check driver session and restart if needed
        if not self.restart_driver_if_needed():
            print("❌ Could not restart driver session")
            return 0
        
        try:
            current_window = self.driver.current_window_handle
        except InvalidSessionIdException:
            print("🔄 Session lost getting current window, restarting driver...")
            if not self.restart_driver_if_needed():
                return 0
            current_window = self.driver.current_window_handle
        
        try:
            self.driver.execute_script(f"window.open('{notice_url}', '_blank');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            
            try:
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                print("⏳ Waiting 2 seconds for page translation...")
                time.sleep(2)
            except TimeoutException:
                print("⏰ Page load timeout, attempting to continue...")
                time.sleep(1)
            
            try:
                page_source = self.driver.page_source
                if len(page_source) < 1000:
                    print("⚠️ Page content too small, skipping...")
                    return 0
                clean_text = self.extract_clean_text(page_source)
                if len(clean_text) < 100:
                    print("⚠️ No meaningful content extracted, skipping...")
                    return 0
            except Exception as e:
                print(f"⚠️ Error extracting page content: {e}")
                return 0
            
            if not self.claude_parser:
                print("⚠️ Claude parser not available")
                return 0
            
            # Quick filter disabled - process all reports with Claude
            # if not self.quick_margin_check(clean_text):
            #     print("⚡ Quick filter: Not a margin notice (skipping Claude)")
            #     return 0
            
            print("🤖 Parsing content with Claude Enhanced Logic...")
            try:
                claude_result = self.claude_parser.parse_margin_notice(clean_text, title)
                print(f"🤖 Claude Enhanced: {claude_result.get('summary', 'No summary available')}")
            except Exception as e:
                print(f"❌ Claude parsing failed: {e}")
                # Log more details about the failure
                if "NoneType" in str(e):
                    print(f"🔍 NoneType error suggests data structure issue in notice: {title}")
                return 0
            
            if not claude_result.get('is_margin_notice', False):
                print("📄 Not a margin ratio adjustment notice")
                return 0
            
            saved_count = 0
            effective_dates = claude_result.get('effective_dates', [])
            print(f"💾 Found {len(effective_dates)} effective dates in notice")
            
            for date_entry in effective_dates:
                effective_date = date_entry.get('date')
                if not effective_date:
                    print(f"⚠️ Skipping entry with missing effective date")
                    continue
                
                commodities = date_entry.get('commodities', [])
                print(f"📅 {effective_date}: processing {len(commodities)} commodities")
                
                for commodity_data in commodities:
                    commodity_name = commodity_data.get('commodity', 'Unknown')
                    hedging_pct = commodity_data.get('hedging_percentage', 0)
                    speculative_pct = commodity_data.get('speculative_percentage', 0)
                    
                    # Handle None values from Claude parsing
                    if hedging_pct is None:
                        hedging_pct = 0
                    if speculative_pct is None:
                        speculative_pct = 0
                    
                    if hedging_pct > 20 or speculative_pct > 20:
                        print(f"⚠️ Skipping {commodity_name}: percentages exceed 20% limit ({hedging_pct}%/{speculative_pct}%)")
                        continue
                    
                    print(f"💾 Saving: {commodity_name} ({hedging_pct}%/{speculative_pct}%) effective {effective_date}")
                    
                    entry = {
                        'notice_date': notice_date.strftime("%Y-%m-%d"),
                        'title': title,
                        'url': notice_url,
                        'commodity': commodity_data['commodity'],
                        'hedging_percentage': hedging_pct,
                        'speculative_percentage': speculative_pct,
                        'effective_date': effective_date,
                        'adjustment_type': commodity_data.get('adjustment_type', 'adjusted_to'),
                        'source_sentence': commodity_data.get('source_sentence', '')[:200],
                        'parsing_method': 'Claude_Enhanced',
                        'confidence': claude_result.get('parsing_confidence', 'medium'),
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    self.append_to_csv(entry)
                    self.extracted_data.append(entry)
                    saved_count += 1
            
            if saved_count > 0:
                unique_commodities = len(set(entry['commodity'] for entry in self.extracted_data if entry['notice_date'] == notice_date.strftime("%Y-%m-%d")))
                print(f"💾 Saved {saved_count} entries for {unique_commodities} commodities")
            
            # Handle reversion notice post-processing - STRICT validation to prevent false positives
            if self.is_valid_reversion_notice(claude_result, title):
                print(f"🔄 Detected VALID reversion notice - will process after all data collected")
                # Store reversion notice info for later processing
                reversion_info = {
                    'notice_date': notice_date,
                    'title': title,
                    'url': notice_url,
                    'claude_result': claude_result,
                    'effective_dates': claude_result.get('effective_dates', [])
                }
                if not hasattr(self, 'reversion_notices'):
                    self.reversion_notices = []
                self.reversion_notices.append(reversion_info)
            elif claude_result.get('is_reversion_notice', False):
                print(f"⚠️ Reversion flag detected but failed validation - NOT processing inference for: {title}")
            
            return saved_count
                
        except TimeoutException:
            print(f"⏰ Timeout processing notice: {title[:50]}...")
            return 0
        except Exception as e:
            print(f"❌ Error scraping notice: {type(e).__name__}: {str(e)[:100]}...")
            return 0
            
        finally:
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                self.driver.switch_to.window(current_window)
                time.sleep(0.5)
            except Exception as e:
                print(f"⚠️ Error closing tab: {e}")
    
    # DISABLED: Quick margin check - now processing all reports with Claude
    # def quick_margin_check(self, content: str) -> bool:
    #     margin_indicators = ['margin ratio', 'trading margin', '保证金', '交易保证金', 'hedging', 'speculative', '套期保值', '投机', 'price limit', '价格限额', 'adjusted to', '调整']
    #     content_lower = content.lower()
    #     matches = sum(1 for indicator in margin_indicators if indicator in content_lower)
    #     is_likely = matches >= 3
    #     if not is_likely:
    #         print(f"⚡ Quick filter: Only {matches}/3+ margin indicators found")
    #     return is_likely
    
    def is_valid_reversion_notice(self, claude_result, title):
        """Strict validation to determine if a notice should trigger reversion inference"""
        
        # Must be flagged as reversion notice by Claude
        if not claude_result.get('is_reversion_notice', False):
            return False
        
        # Must have reversion details
        reversion_details = claude_result.get('reversion_details', {})
        if not reversion_details.get('has_reversion_clause', False):
            return False
        
        # Must have reversion text containing key phrases
        reversion_text = reversion_details.get('reversion_text', '').lower()
        required_phrases = [
            'revert to their original levels',
            'revert to original levels', 
            'restored to their original levels',
            'unless otherwise specified',
            '恢复原水平',
            '恢复到原来水平',
            '恢复至原有水平',  # Added Chinese phrase from the actual notice
            'revert to original',
            'restore to original'
        ]
        
        if not any(phrase in reversion_text for phrase in required_phrases):
            print(f"🚫 Reversion text doesn't contain required phrases: {reversion_text}")
            return False
        
        # Must have multiple effective dates OR explicit + implicit commodities
        effective_dates = claude_result.get('effective_dates', [])
        if len(effective_dates) < 2:
            # Single date notices should only be reversion if they have explicit + implicit pattern
            if len(effective_dates) == 1:
                commodities = effective_dates[0].get('commodities', [])
                # Look for pattern where few commodities are explicit but notice says "others revert"
                if len(commodities) > 5:  # If many commodities are explicit, probably not reversion
                    print(f"🚫 Too many explicit commodities ({len(commodities)}) for single-date reversion")
                    return False
            else:
                print(f"🚫 No effective dates found")
                return False
        
        # Must be holiday-related notice (most reversion notices are holiday work arrangements)
        holiday_keywords = [
            'holiday', 'festival', 'day', 'arrangements', 'work arrangements',
            '节', '假期', '工作安排', '节假日', 'labor day', 'spring festival', 
            'national day', 'dragon boat', '劳动节', '春节', '国庆节', '端午节'
        ]
        
        title_lower = title.lower()
        if not any(keyword in title_lower for keyword in holiday_keywords):
            print(f"🚫 Title doesn't contain holiday keywords: {title}")
            return False
        
        print(f"✅ Reversion notice validation passed for: {title}")
        return True

    def process_reversion_notices(self):
        """Process all collected reversion notices to infer missing margin ratios"""
        if not hasattr(self, 'reversion_notices') or not self.reversion_notices:
            return 0
        
        print(f"\n🔄 Processing {len(self.reversion_notices)} reversion notices...")
        total_inferred = 0
        
        for reversion_info in self.reversion_notices:
            try:
                inferred_count = self.process_single_reversion_notice(reversion_info)
                total_inferred += inferred_count
            except Exception as e:
                print(f"❌ Error processing reversion notice: {e}")
                continue
        
        print(f"🔄 Reversion processing complete: {total_inferred} entries inferred")
        return total_inferred
    
    def process_single_reversion_notice(self, reversion_info):
        """Process a single reversion notice to infer margin ratios for unlisted commodities"""
        effective_dates = reversion_info['effective_dates']
        inferred_count = 0
        
        # All known SHFE commodities
        all_commodities = [
            'Copper', 'Aluminum', 'Zinc', 'Lead', 'Nickel', 'Tin', 'Alumina', 
            'Gold', 'Silver', 'Rebar', 'Hot-rolled Coil', 'Wire Rod', 'Stainless Steel',
            'Fuel Oil', 'Petroleum Asphalt', 'Butadiene Rubber', 'Natural Rubber', 
            'Pulp', 'Crude Oil', 'Low-sulfur Fuel Oil'
        ]
        
        for date_entry in effective_dates:
            effective_date = date_entry.get('date')
            if not effective_date:
                continue
                
            # Get commodities explicitly mentioned in this reversion notice
            explicit_commodities = [c['commodity'] for c in date_entry.get('commodities', [])]
            print(f"📅 {effective_date}: Found explicit commodities: {explicit_commodities}")
            
            # Find commodities that should revert (not explicitly mentioned)
            commodities_to_revert = [c for c in all_commodities if c not in explicit_commodities]
            print(f"🔄 Commodities needing reversion inference: {commodities_to_revert}")
            
            # Find baseline ratios for these commodities (last known non-holiday rates)
            for commodity in commodities_to_revert:
                # CRITICAL: Check if this commodity+date already exists to prevent data corruption
                existing_entry = self.find_existing_entry(commodity, effective_date)
                if existing_entry:
                    print(f"🛡️ PROTECTED: {commodity} on {effective_date} already exists - skipping inference")
                    continue
                
                baseline_ratios = self.find_baseline_ratios(commodity, effective_date)
                if baseline_ratios:
                    # Create inferred entry
                    entry = {
                        'notice_date': reversion_info['notice_date'].strftime("%Y-%m-%d"),
                        'title': reversion_info['title'] + " [INFERRED REVERSION]",
                        'url': reversion_info['url'],
                        'commodity': commodity,
                        'hedging_percentage': baseline_ratios['hedging'],
                        'speculative_percentage': baseline_ratios['speculative'],
                        'effective_date': effective_date,
                        'adjustment_type': 'reverted_to_original',
                        'source_sentence': f'Inferred from reversion notice: {reversion_info["claude_result"].get("reversion_details", {}).get("reversion_text", "")}',
                        'parsing_method': 'Reversion_Inference',
                        'confidence': 'medium',
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    print(f"💾 Inferring reversion: {commodity} → {baseline_ratios['hedging']}%/{baseline_ratios['speculative']}% on {effective_date}")
                    self.append_to_csv(entry)
                    self.extracted_data.append(entry)
                    inferred_count += 1
                else:
                    print(f"⚠️ Could not find baseline ratios for {commodity}")
        
        return inferred_count
    
    def find_existing_entry(self, commodity, effective_date):
        """Check if an entry already exists for this commodity and effective date"""
        for entry in self.extracted_data:
            if (entry['commodity'] == commodity and 
                entry['effective_date'] == effective_date):
                return entry
        return None
    
    def find_baseline_ratios(self, commodity, effective_date):
        """Find the last known non-holiday margin ratios for a commodity before the given date"""
        try:
            effective_date_obj = datetime.strptime(effective_date, "%Y-%m-%d").date()
        except:
            return None
        
        # Holiday keywords that indicate temporary adjustments
        holiday_keywords = ['holiday', 'festival', '节', 'day', 'labor', 'spring', 'national', 'dragon boat']
        
        # First try to find from extracted data (for commodities we've already processed)
        commodity_entries = []
        for entry in self.extracted_data:
            if (entry['commodity'] == commodity and 
                entry['effective_date'] < effective_date and
                not any(keyword.lower() in entry['title'].lower() for keyword in holiday_keywords)):
                commodity_entries.append(entry)
        
        if commodity_entries:
            # Sort by effective date and get the most recent non-holiday entry
            commodity_entries.sort(key=lambda x: x['effective_date'], reverse=True)
            latest_entry = commodity_entries[0]
            
            return {
                'hedging': latest_entry['hedging_percentage'],
                'speculative': latest_entry['speculative_percentage'],
                'source_date': latest_entry['effective_date']
            }
        
        # Fallback: Use known baseline ratios for SHFE commodities 
        # Based on reference file data from early 2025 (pre-holiday normal rates)
        baseline_ratios = {
            'Copper': (8, 9),           # From 2025-02-05 reference data
            'Aluminum': (8, 9),         # From 2025-02-05 reference data  
            'Zinc': (8, 9),             # From 2025-02-05 reference data
            'Lead': (8, 9),             # From 2025-02-05 reference data
            'Nickel': (11, 12),         # From 2025-02-05 reference data
            'Tin': (11, 12),            # From 2025-02-05 reference data
            'Alumina': (8, 9),          # From 2025-02-05 reference data
            'Gold': (13, 14),           # From 2025-02-05 reference data (most recent stable)
            'Silver': (12, 13),         # From 2025-02-05 reference data
            'Rebar': (6, 7),            # From 2025-02-05 reference data
            'Hot-rolled Coil': (6, 7),  # From 2025-02-05 reference data
            'Wire Rod': (8, 9),         # From 2025-02-05 reference data
            'Stainless Steel': (6, 7),  # From 2025-02-05 reference data
            'Fuel Oil': (8, 9),         # From 2025-02-05 reference data
            'Petroleum Asphalt': (8, 9), # From 2025-02-05 reference data
            'Butadiene Rubber': (8, 9),  # From 2025-02-05 reference data
            'Natural Rubber': (7, 8),    # From 2025-02-05 reference data
            'Pulp': (7, 8),             # From 2025-02-05 reference data
            'Crude Oil': (9, 10),       # Estimated from typical ratios
            'Low-sulfur Fuel Oil': (9, 10) # Estimated from typical ratios
        }
        
        if commodity in baseline_ratios:
            hedging, speculative = baseline_ratios[commodity]
            print(f"📊 Using historical baseline for {commodity}: {hedging}%/{speculative}%")
            return {
                'hedging': hedging,
                'speculative': speculative,
                'source_date': 'historical_baseline'
            }
        
        print(f"⚠️ No baseline ratios found for {commodity}")
        return None

    def append_to_csv(self, data: Dict):
        with open(self.csv_output, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([data['notice_date'], data['title'], data['url'], data['commodity'], data['hedging_percentage'], data['speculative_percentage'], data['effective_date'], data['adjustment_type'], data['source_sentence'], data['parsing_method'], data['confidence'], data['scraped_at']])
    
    def load_initial_page_with_retry(self) -> bool:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"🌐 Loading main page (attempt {attempt + 1}/{max_retries})...")
                self.driver.get(self.base_url)
                try:
                    self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                    print("✅ Main page loaded successfully")
                    time.sleep(2)
                    return True
                except TimeoutException:
                    print(f"⏰ Page load timeout on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        print("🔄 Retrying...")
                        time.sleep(2)
                    continue
            except Exception as e:
                print(f"❌ Error loading page (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    print("🔄 Retrying...")
                    time.sleep(3)
                continue
        print("❌ Failed to load main page after all retries")
        return False
    
    def process_notices_on_page_safe(self, page_num: int) -> Tuple[int, int, int]:
        processed_count = 0
        extracted_count = 0
        claude_calls_saved = 0  # No longer used - processing all reports
        skipped_count = 0  # Track skipped notices
        
        try:
            try:
                self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "detail_content")))
            except TimeoutException:
                print(f"⏰ Timeout waiting for page content on page {page_num}")
                try:
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".table_item_info")))
                except TimeoutException:
                    print(f"❌ Could not find notice content on page {page_num}")
                    return 0, 0, 0
            
            try:
                notice_items = self.driver.find_elements(By.CSS_SELECTOR, ".table_item_info")
                if not notice_items:
                    print(f"⚠️ No notice items found on page {page_num}")
                    return 0, 0, 0
                print(f"📋 Found {len(notice_items)} notices on page {page_num}")
            except Exception as e:
                print(f"❌ Error finding notice items: {e}")
                return 0, 0, 0
            
            for idx, item in enumerate(notice_items):
                print(f"📋 Processing notice {idx + 1}/{len(notice_items)} on page {page_num}")
                try:
                    try:
                        date_element = item.find_element(By.CSS_SELECTOR, ".info_item_date")
                        date_text = date_element.text.strip()
                        notice_date = self.parse_date(date_text)
                    except InvalidSessionIdException:
                        print(f"🔄 Session lost extracting date from notice {idx + 1}, restarting driver...")
                        if not self.restart_driver_if_needed():
                            return processed_count, extracted_count, claude_calls_saved
                        # Need to reload the page and re-find items
                        return processed_count, extracted_count, claude_calls_saved
                    except Exception as e:
                        print(f"⚠️ Could not extract date from notice {idx + 1}: {e}")
                        continue
                    
                    if not self.is_date_in_range(notice_date):
                        skipped_count += 1
                        print(f"⏭️ Skipping notice {idx + 1}: date {notice_date} outside range {self.start_date} to {self.today}")
                        continue
                    
                    try:
                        title_element = item.find_element(By.CSS_SELECTOR, ".info_item_title a")
                        title = title_element.get_attribute("title") or title_element.text
                        relative_url = title_element.get_attribute("href")
                    except Exception as e:
                        print(f"⚠️ Could not extract title/URL from notice {idx + 1}: {e}")
                        continue
                    
                    # DISABLED: Title filtering - processing all notices to avoid missing data
                    # Many margin notices have generic titles but contain margin data in content
                    # if not self.is_likely_margin_notice(title):
                    #     claude_calls_saved += 1
                    #     continue
                    
                    if relative_url.startswith("./"):
                        full_url = self.base_url + relative_url[2:]
                    elif relative_url.startswith("/"):
                        full_url = "https://www.shfe.com.cn" + relative_url
                    else:
                        full_url = relative_url
                    
                    processed_count += 1
                    print(f"\n🎯 Processing ({processed_count}): {title} ({date_text})")
                    print(f"    📄 Notice date: {notice_date}, URL: {full_url}")
                    
                    try:
                        margin_count = self.scrape_notice_content(full_url, title, notice_date)
                        extracted_count += margin_count
                    except Exception as e:
                        print(f"⚠️ Error processing notice content: {e}")
                        continue
                except Exception as e:
                    print(f"❌ Error processing notice {idx + 1}: {e}")
                    continue
            
            # Title filtering disabled - processing all notices
            # if claude_calls_saved > 0:
            #     print(f"⚡ Saved {claude_calls_saved} Claude calls via title filtering")
            print(f"📊 Page {page_num} summary: {len(notice_items)} total notices, {processed_count} processed, {skipped_count} skipped (outside date range)")
        except Exception as e:
            print(f"❌ Critical error on page {page_num}: {e}")
            
        return processed_count, extracted_count, claude_calls_saved
    
    def parse_date(self, date_str: str) -> Optional[date]:
        try:
            return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None
    
    def is_date_in_range(self, notice_date: Optional[date]) -> bool:
        if notice_date is None:
            return False
        return self.start_date <= notice_date <= self.today
    
    def navigate_to_next_page(self) -> bool:
        try:
            # Check driver session first
            if not self.restart_driver_if_needed():
                return False
            
            next_selectors = [".btn-next:not([disabled])", ".el-pagination__next:not(.is-disabled)", ".pagination-next:not(.disabled)"]
            next_button = None
            for selector in next_selectors:
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue
            if not next_button:
                print("➡️ No next button found - reached end of pagination")
                return False
            
            print(f"🔄 Clicking next page button using selector: {[s for s in next_selectors if next_button.tag_name in s or selector in str(next_button)]}")
            next_button.click()
            time.sleep(2)
            
            try:
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                return True
            except TimeoutException:
                print("⏰ Timeout after clicking next page")
                return False
        except InvalidSessionIdException:
            print("🔄 Session lost during navigation, restarting driver...")
            if self.restart_driver_if_needed():
                return False  # Need to restart processing from beginning
            return False
        except Exception as e:
            print(f"❌ Error navigating to next page: {e}")
            return False
    
    def export_final_data(self) -> str:
        if not self.extracted_data:
            return ""
        
        latest_date = max(entry['scraped_at'] for entry in self.extracted_data)
        release_date = datetime.fromisoformat(latest_date.replace('T', ' ').split('.')[0]).strftime("%Y-%m-%d")
        
        data_path, meta_path = self.data_exporter.create_xls_files(self.extracted_data, release_date)
        zip_path = self.data_exporter.create_zip_archive(data_path, meta_path)
        
        return zip_path
    
    def run_scraper(self):
        """Main execution. Returns path to the final ZIP file or None."""
        print("🚀 Starting LLM-Enhanced SHFE Scraper with Improved Logic")
        print(f"📊 Dataset: {self.dataset_name}")
        print(f"📅 Date range: {self.start_date_str} to {self.today}")
        print(f"🤖 Claude content parsing: {'Enabled' if self.claude_parser else 'Disabled'}")
        
        try:
            self.setup_driver()
            self.setup_csv()

            if not self.load_initial_page_with_retry():
                print("❌ Could not load main page. Exiting.")
                return None
            
            page_count = 0
            total_processed = 0
            total_extracted = 0
            pages_without_data = 0
            
            while True:
                page_count += 1
                print(f"\n📄 Processing page {page_count}")
                
                processed, extracted, _ = self.process_notices_on_page_safe(page_count)
                total_processed += processed
                total_extracted += extracted
                
                if processed == 0: 
                    pages_without_data += 1
                    print(f"📄 No margin notices found on page {page_count} ({pages_without_data} consecutive empty pages)")
                else: 
                    pages_without_data = 0
                    print(f"📄 Found {processed} margin notices on page {page_count}")
                
                if pages_without_data > 10 or page_count > 50:
                    print(f"🛑 Stopping: {pages_without_data} empty pages or reached {page_count} pages")
                    break
                
                if not self.navigate_to_next_page():
                    break
            
            print(f"\n🎉 Scraping completed!")
            print(f"🎯 Total entries extracted: {total_extracted}")
            
            # Process reversion notices to infer missing margin ratios
            reversion_count = self.process_reversion_notices()
            total_extracted += reversion_count
            
            if total_extracted > 0:
                print(f"📊 Final dataset: {total_extracted} total entries (including {reversion_count} inferred)")
                zip_path = self.export_final_data()
                print(f"📦 Runbook ZIP created at: {zip_path}")
                return zip_path
            else:
                print("💡 No new margin data found in the specified date range.")
                return None
            
        except Exception as e:
            print(f"❌ Critical scraping error: {e}")
            return None
        finally:
            if self.driver:
                self.driver.quit()