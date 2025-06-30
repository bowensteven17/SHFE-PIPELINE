#!/usr/bin/env python3
"""
LLM-Enhanced SHFE Margin Scraper
Enhanced with improved extraction logic from Claude script + Gemini parsing
Uses incremental batching, crash recovery, and focused margin data extraction
"""
import time
import csv
import re
import os
import json
import xlwt
import zipfile
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Tuple
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Gemini integration
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    print("⚠️ Google Generative AI not installed. Run: pip install google-generativeai")
    GEMINI_AVAILABLE = False

class SHFEDataExporter:
    """Export data in runbook format with correct headers - FOCUSED ON MARGIN DATA"""
    def __init__(self, dataset_name: str, output_dir: str):  # Fixed: __init__ instead of init
        self.dataset_name = dataset_name
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
    
    def create_xls_files(self, data_entries: List[Dict], release_date: str) -> Tuple[str, str]:
        """Create DATA and META XLS files - FOCUSED on margin data only"""
        timestamp = datetime.now().strftime("%Y%m%d")
        data_filename = f"{self.dataset_name}_DATA_{timestamp}.xls"
        meta_filename = f"{self.dataset_name}_META_{timestamp}.xls"
        
        data_path = os.path.join(self.output_dir, data_filename)
        meta_path = os.path.join(self.output_dir, meta_filename)
        
        self._create_data_file_margin_focused(data_entries, data_path)
        self._create_meta_file_margin_focused(meta_path, release_date, data_entries)
        
        return data_path, meta_path
    
    def _create_data_file_margin_focused(self, data_entries: List[Dict], filepath: str):  # Fixed: method name
        """Create DATA XLS file with correct header format - MARGIN DATA ONLY"""
        workbook = xlwt.Workbook(encoding='utf-8')
        worksheet = workbook.add_sheet('Data')
        
        # Enhanced commodity name standardization mapping from second script
        commodity_name_mapping = {
            'Aluminum': 'Aluminium',  # Use British spelling
            'Petroleum Asphalt': 'Petroleum Asphalt ',  # Note the extra space
            'Natural Rubber': 'Natural Rubber',  # Includes No. 20 rubber
            'Low-sulfur Fuel Oil': 'Low-sulfur Fuel Oil',
            'Hot-rolled Coil': 'Hot-rolled Coil',
            'Wire Rod': 'Wire Rod',
            'Butadiene Rubber': 'Butadiene Rubber',
            'Stainless Steel': 'Stainless Steel',
            'Crude Oil': 'Crude Oil'
        }
        
        # Group data by effective date
        data_by_date = {}
        time_series_info = {}  # Store both code and description
        
        for entry in data_entries:
            effective_date = entry.get('effective_date', '')
            commodity = entry.get('commodity', 'UNKNOWN')
            
            # Skip non-margin entries
            if entry.get('entry_type') != 'margin_data':
                continue
                
            # Handle None or empty commodity names
            if not commodity or commodity.lower() in ['none', 'unknown', '']:
                continue
                
            # Apply commodity name mapping for headers
            display_commodity = commodity_name_mapping.get(commodity, commodity)
            
            if effective_date not in data_by_date:
                data_by_date[effective_date] = {}
            
            # Create proper time series codes (use original commodity name for codes)
            commodity_clean = commodity.upper().replace(' ', '').replace('-', '_')  # Fixed: variable name
            hedging_code = f"{commodity_clean}_HEDGING_MARGIN"
            speculative_code = f"{commodity_clean}_SPECULATIVE_MARGIN"
            
            # Create proper descriptions in the required format (use display name)
            hedging_description = f"{display_commodity}: Margin ratio for hedging transactions"
            speculative_description = f"{display_commodity}: Margin ratio for speculative transactions"
            
            hedging_pct = entry.get('hedging_percentage', '')
            speculative_pct = entry.get('speculative_percentage', '')
            
            # Store data
            data_by_date[effective_date][hedging_code] = hedging_pct
            data_by_date[effective_date][speculative_code] = speculative_pct
            
            # Store time series info (code -> description mapping)
            time_series_info[hedging_code] = hedging_description
            time_series_info[speculative_code] = speculative_description
        
        if not data_by_date:
            # Create empty sheet with headers
            worksheet.write(0, 0, "DATE")
            worksheet.write(1, 0, "No margin data available")
            workbook.save(filepath)
            return
        
        # Write headers - CORRECT FORMAT from second script
        sorted_codes = sorted(time_series_info.keys())
        
        # First row: TIME SERIES CODES
        worksheet.write(0, 0, "DATE")
        for col_idx, code in enumerate(sorted_codes, 1):
            worksheet.write(0, col_idx, code)
        
        # Second row: DESCRIPTIONS (the correct format)
        worksheet.write(1, 0, "Reporting Date")
        for col_idx, code in enumerate(sorted_codes, 1):
            description = time_series_info[code]
            worksheet.write(1, col_idx, description)
        
        # Write data rows
        sorted_dates = sorted([date for date in data_by_date.keys() if date])
        for row_idx, effective_date in enumerate(sorted_dates, 2):
            worksheet.write(row_idx, 0, effective_date)
            for col_idx, code in enumerate(sorted_codes, 1):
                value = data_by_date[effective_date].get(code, "")
                worksheet.write(row_idx, col_idx, value)
        
        workbook.save(filepath)
        print(f"✅ Created margin-focused DATA file: {filepath}")
    
    def _create_meta_file_margin_focused(self, filepath: str, release_date: str, data_entries: List[Dict]):  # Fixed: method name
        """Create META XLS file with correct descriptions - MARGIN DATA ONLY"""
        workbook = xlwt.Workbook(encoding='utf-8')
        worksheet = workbook.add_sheet('Metadata')
        
        headers = [
            'TIMESERIES_ID', 'TIMESERIES_DESCRIPTION', 'UNIT', 'FREQUENCY',
            'SOURCE', 'DATASET', 'LAST_RELEASE_DATE', 'NEXT_RELEASE_DATE'
        ]
        
        for col_idx, header in enumerate(headers):
            worksheet.write(0, col_idx, header)
        
        # Get unique commodities from actual margin data
        commodities_in_data = set()
        for entry in data_entries:
            if entry.get('entry_type') == 'margin_data':
                commodity = entry.get('commodity')
                if commodity and commodity.lower() not in ['none', 'unknown', '']:
                    commodities_in_data.add(commodity)
        
        # Enhanced commodity name mapping for metadata
        commodity_display_mapping = {
            'Aluminum': 'Aluminium',
            'Petroleum Asphalt': 'Petroleum Asphalt ',
        }
        
        transaction_types = [
            ('HEDGING', 'hedging transactions'),
            ('SPECULATIVE', 'speculative transactions')
        ]
        
        row_idx = 1
        for commodity in sorted(commodities_in_data):
            for transaction_code, transaction_desc in transaction_types:
                # For timeseries ID, use normalized name
                normalized_commodity = commodity.replace('Aluminium', 'Aluminum').strip()
                timeseries_id = f"{normalized_commodity.upper().replace(' ', '').replace('-', '')}_{transaction_code}_MARGIN"  # Fixed: variable name
                
                # For description, use exact display name
                display_commodity = commodity_display_mapping.get(commodity, commodity)
                description = f"{display_commodity}: Margin ratio for {transaction_desc}"
                
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
        print(f"✅ Created margin-focused META file: {filepath}")
    
    def create_zip_archive(self, data_path: str, meta_path: str) -> str:
        """Create ZIP archive"""
        timestamp = datetime.now().strftime("%Y%m%d")
        zip_filename = f"{self.dataset_name}_{timestamp}.ZIP"  # Fixed: variable name
        zip_path = os.path.join(self.output_dir, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(data_path, os.path.basename(data_path))
            zipf.write(meta_path, os.path.basename(meta_path))
        
        print(f"📦 Created ZIP archive: {zip_path}")
        return zip_path

class EnhancedGeminiContentParser:
    """Gemini-powered intelligent content parsing with ENHANCED logic from second script"""
    def __init__(self, api_key: str):  # Fixed: __init__ instead of init
        if not GEMINI_AVAILABLE:
            raise ImportError("Google Generative AI library not available")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
    
    def parse_margin_notice(self, notice_content: str, notice_title: str) -> Dict:
        """Enhanced Gemini parsing with improved logic from second script"""
        prompt = f"""You are an expert at parsing Shanghai Futures Exchange (SHFE) and Shanghai International Energy Exchange margin ratio notices. Your job is to extract ALL margin ratio data with PERFECT accuracy using the enhanced parsing logic.

NOTICE TITLE: {notice_title}
NOTICE CONTENT: {notice_content}

ENHANCED PARSING RULES (from improved extraction logic):
1. EFFECTIVE DATE IDENTIFICATION PATTERNS:
   - PRIMARY: "trading margin ratio and price limit range will be adjusted as follows" 
   - SECONDARY: "trading margin ratio will be adjusted as follows"
   - The date is usually mentioned BEFORE these phrases in the same sentence
   - Look for: "Starting from the closing settlement on [DATE]" or "from the closing settlement on [DATE]"
   - Look for: "After trading on [DATE], starting from the closing settlement of the first trading day"

2. COMMODITY FILTERING (ENHANCED):
   - INCLUDE ONLY physical commodities: copper, aluminum, zinc, lead, nickel, tin, alumina, gold, silver, rebar, hot-rolled coil, wire rod, stainless steel, fuel oil, petroleum asphalt, butadiene rubber, natural rubber, pulp, crude oil, low-sulfur fuel oil, No. 20 rubber, international copper
   - EXCLUDE financial indices: container shipping index, freight rates, any "index" contracts
   - EXCLUDE non-commodity contracts

3. MULTIPLE COMMODITIES IN ONE SENTENCE (CRITICAL):
   - When sentence mentions "aluminum, zinc, lead, alumina, wire rod and pulp futures contracts were adjusted to 9%, margin ratio for hedging transactions was adjusted to 10%, and speculative transactions to 11%"
   - Extract as SEPARATE entries:
     * commodity=(Aluminum) Hedging_Percentage=(10) Speculative_Percentage=(11)
     * commodity=(Zinc) Hedging_Percentage=(10) Speculative_Percentage=(11)
     * commodity=(Lead) Hedging_Percentage=(10) Speculative_Percentage=(11)
     * commodity=(Alumina) Hedging_Percentage=(10) Speculative_Percentage=(11)
     * commodity=(Wire Rod) Hedging_Percentage=(10) Speculative_Percentage=(11)
     * commodity=(Pulp) Hedging_Percentage=(10) Speculative_Percentage=(11)

4. HANDLING SPECIAL STATEMENTS:
   - "remains at X%" → Extract the actual percentage value, mark as "remains_at"
   - "restored to their original levels" → Mark as "restored_to_original"
   - ALWAYS extract the margin ratios (hedging/speculative), NOT price limits

5. VALIDATION RULES (ENHANCED):
   - All margin percentages must be ≤ 20%
   - If percentage > 20%, exclude that commodity (likely not a physical commodity)
   - Hedging percentage should be ≤ Speculative percentage (usually)

6. COMMODITY NAME STANDARDIZATION (ENHANCED):
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

OUTPUT FORMAT (JSON only):
{{
    "is_margin_notice": true/false,
    "effective_dates": [
        {{
            "date": "YYYY-MM-DD",
            "date_source": "exact text showing this date",
            "commodities": [
                {{
                    "commodity": "standardized name",
                    "hedging_percentage": number,
                    "speculative_percentage": number,
                    "adjustment_type": "adjusted_to/remains_at/restored_to_original",
                    "source_sentence": "exact sentence with this data"
                }}
            ]
        }}
    ],
    "total_commodities": number,
    "total_entries": number,
    "parsing_confidence": "high/medium/low",
    "excluded_non_commodities": ["list of excluded items like indices"]
}}

CRITICAL REQUIREMENTS:
- Return ONLY valid JSON
- Extract margin ratios, NOT price limits
- Duplicate data for multiple commodities in same sentence
- Validate percentages ≤ 20%
- Exclude financial indices and non-physical commodities
- Use exact standardized commodity names
"""
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    response_mime_type="application/json"
                )
            )
            result_text = response.text.strip()
            
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
                
                print(f"🤖 Gemini Enhanced: Found {total_entries} entries for {total_commodities} commodities across {total_dates} dates")
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
                        if hedging > 20 or speculative > 20:
                            invalid_percentages.append(f"{commodity.get('commodity')}({hedging}%/{speculative}%)")
                    
                    print(f"📅 {date}: {commodity_count} commodities")
                    if invalid_percentages:
                        print(f"⚠️ Validation warnings for {date}: {invalid_percentages}")
            else:
                print(f"🤖 Gemini Enhanced: Not a margin ratio adjustment notice")
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"❌ Gemini JSON parsing error: {e}")
            print(f"Raw response: {result_text[:300]}...")
            return {"is_margin_notice": False, "effective_dates": [], "parsing_confidence": "low"}
        except Exception as e:
            print(f"❌ Gemini parsing failed: {e}")
            return {"is_margin_notice": False, "effective_dates": [], "parsing_confidence": "low"}

class SHFECommodityExtractor:
    """Enhanced commodity patterns from second script"""
    def __init__(self):  # Fixed: __init__ instead of init
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
        
        # Non-commodity patterns to exclude (from second script)
        self.excluded_patterns = [
            'container shipping index', 'freight', 'index', 'shipping', 'csi',
            'financial index', 'stock index', 'bond', 'currency'
        ]

class EnhancedMarginInterestDetector:
    """
    ENHANCED interest detection focused on margin adjustments only (from second script)
    More restrictive filtering for better precision
    """
    def __init__(self):  # Fixed: __init__ instead of init
        # Enhanced margin-specific detection
        self.margin_keywords = [
            'margin', 'ratio', '保证金', '比例', '调整', 'adjust', 
            'price limits', '涨跌停板', 'notice', '通知',
            'hedging', 'speculative', '套期保值', '投机'
        ]
        
        # Strong margin indicators from second script
        self.strong_indicators = [
            "保证金比例", "交易保证金", "margin ratio", "price limit",
            "端午节", "劳动节", "春节", "国庆节", "中秋节",  # Holiday adjustments
            "Dragon Boat", "Labor Day", "Spring Festival", "National Day"
        ]
        
        # Weak indicators - need multiple to trigger processing
        self.weak_indicators = [
            "保证金", "限额", "调整", "margin", "ratio", "limit",
            "节假日", "holiday", "festival", "通知", "notice"
        ]
        
        # Commodity keywords for enhanced detection
        self.commodity_keywords = [
            "copper", "铜", "aluminum", "铝", "zinc", "锌", "lead", "铅", "tin", "锡", "nickel", "镍", 
            "gold", "黄金", "silver", "白银", "rebar", "螺纹钢", "fuel oil", "燃料油",
            "steel", "钢", "pulp", "纸浆", "alumina", "氧化铝", "asphalt", "沥青",
            "rubber", "橡胶", "期货", "futures"
        ]
        
        # Enhanced minimum threshold for margin notices
        self.min_relevance_score = 10.0  # Higher threshold for precision
    
    def is_likely_margin_notice(self, title: str) -> bool:
        """Enhanced pre-filter notices with better margin detection (from second script)"""
        title_lower = title.lower()
        
        # Check strong indicators first
        if any(indicator in title_lower or indicator in title for indicator in self.strong_indicators):
            print(f"🎯 Strong margin indicator found in title")
            return True
        
        # Check weak indicators - need at least 2
        weak_matches = sum(1 for indicator in self.weak_indicators 
                          if indicator in title_lower or indicator in title)
        if weak_matches >= 2:
            print(f"🎯 Multiple weak indicators ({weak_matches}) found in title")
            return True
        
        print(f"⏭️ No sufficient margin indicators in title")
        return False
    
    def calculate_margin_relevance_score(self, context_data: dict) -> tuple:
        """Calculate relevance score focused on margin adjustments only"""
        title = context_data.get('title', '').lower()
        full_context = context_data.get('full_context', '').lower()
        relevance_score = 0
        matched_details = []
        mentioned_commodities = []
        
        # 1. PRIMARY: Margin adjustment notices (HIGHEST SCORES)
        margin_primary_patterns = [
            "notice on adjusting the margin ratio and price limits",
            "关于调整.*保证金比例.*涨跌停板.*通知",
            "关于调整.*保证金比例.*通知", 
            "调整.*保证金比例.*涨跌停板",
            "调整.*交易保证金.*通知"
        ]
        for pattern in margin_primary_patterns:
            if re.search(pattern, title, re.IGNORECASE) or re.search(pattern, full_context, re.IGNORECASE):
                relevance_score += 30  # VERY HIGH score for margin adjustments
                matched_details.append("margin_adjustment_primary")
                break
        
        # 2. Holiday margin adjustments (SPECIAL CASE)
        holiday_patterns = [
            "端午节", "劳动节", "春节", "国庆节", "中秋节",
            "Dragon Boat", "Labor Day", "Spring Festival", "National Day", "holiday"
        ]
        for holiday in holiday_patterns:
            if holiday.lower() in title or holiday.lower() in full_context:
                relevance_score += 15  # High score for holiday adjustments
                matched_details.append("holiday_margin_adjustment")
                break
        
        # 3. Margin-specific keywords
        margin_keyword_count = sum(1 for kw in self.margin_keywords if kw.lower() in full_context)
        if margin_keyword_count > 0:
            relevance_score += min(margin_keyword_count * 2, 10)  # Up to 10 points
            matched_details.append(f"margin_keywords:{margin_keyword_count}")
        
        # 4. Commodity detection (focused on physical commodities)
        commodity_count = sum(1 for kw in self.commodity_keywords if kw.lower() in full_context)
        if commodity_count > 0:
            relevance_score += min(commodity_count * 2, 8)  # Up to 8 points for commodities
            mentioned_commodities.extend([kw for kw in self.commodity_keywords[:3] if kw.lower() in full_context])
            matched_details.append(f"commodities:{commodity_count}")
        
        # 5. Exchange name detection
        exchange_keywords = [
            "上海期货交易所", "上海国际能源交易中心", "SHFE", "INE",
            "Shanghai Futures Exchange", "Shanghai International Energy Exchange"
        ]
        exchange_detected = any(kw.lower() in full_context for kw in exchange_keywords)
        if exchange_detected:
            relevance_score += 2
            matched_details.append("official_exchange_announcement")
        
        # 6. EXCLUSIONS - Strong penalties for non-margin notices
        exclusion_patterns = [
            "关于同意.*品牌.*注册.*公告",       # Brand registration
            "关于就.*征求意见.*公告",           # Public consultation
            "关于注销.*注册.*资质.*公告",       # Registration cancellation  
            "关于.*人事.*任免.*公告",           # Personnel appointments
            "关于.*会议.*纪要.*公告",           # Meeting minutes
            "仓库.*库容.*公告",                 # Warehouse announcements
            "delivery.*suspend"                  # Delivery operations
        ]
        for pattern in exclusion_patterns:
            if re.search(pattern, title, re.IGNORECASE):
                relevance_score -= 20  # Strong penalty for non-margin notices
                matched_details.append("excluded_non_margin")
                break
        
        return relevance_score, matched_details, mentioned_commodities
    
    def extract_notice_context(self, notice_element) -> dict:
        """Extract comprehensive context around a notice element"""
        context_data = {
            'title': '',
            'date_text': '',
            'parent_context': '',
            'full_context': '',
            'href': ''
        }
        
        try:
            # Extract title and URL
            title_element = notice_element.find_element(By.CSS_SELECTOR, ".info_item_title a")
            context_data['title'] = title_element.get_attribute("title") or title_element.text
            context_data['href'] = title_element.get_attribute("href")
        except:
            try:
                # Fallback title extraction
                title_element = notice_element.find_element(By.TAG_NAME, "a")
                context_data['title'] = title_element.text
                context_data['href'] = title_element.get_attribute("href")
            except:
                pass
        
        try:
            # Extract date context
            date_element = notice_element.find_element(By.CSS_SELECTOR, ".info_item_date")
            context_data['date_text'] = date_element.text.strip()
        except:
            # Look for any date-like patterns in the element
            element_text = notice_element.text
            date_match = re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', element_text)
            if date_match:
                context_data['date_text'] = date_match.group(0)
        
        try:
            # Extract parent context
            parent_text = notice_element.get_attribute('textContent') or notice_element.text
            context_data['parent_context'] = parent_text.strip()
        except:
            pass
        
        # Create full context combining all available information
        context_parts = [
            context_data['title'],
            context_data['date_text'],
            context_data['parent_context']
        ]
        context_data['full_context'] = ' '.join([part for part in context_parts if part]).strip()
        
        return context_data
    
    def is_notice_interesting(self, notice_element) -> dict:
        """Enhanced interest detection focused on margin adjustments only"""
        try:
            # Extract comprehensive context
            context_data = self.extract_notice_context(notice_element)
            
            if not context_data['title']:
                return {
                    'is_interesting': False,
                    'reason': 'No title found',
                    'score': 0,
                    'details': [],
                    'commodities': []
                }
            
            # Calculate margin-focused relevance score
            relevance_score, matched_details, mentioned_commodities = self.calculate_margin_relevance_score(context_data)
            
            # Apply threshold for margin notices only
            is_interesting = relevance_score >= self.min_relevance_score
            
            # Enhanced logging
            title_preview = context_data['title'][:100] + "..." if len(context_data['title']) > 100 else context_data['title']
            if is_interesting:
                reason = f"MARGIN NOTICE (score: {relevance_score:.1f}): {', '.join(matched_details)}"
            else:
                reason = f"FILTERED OUT (score: {relevance_score:.1f}): {', '.join(matched_details) if matched_details else 'No margin indicators'}"
                if relevance_score < 5:
                    reason += " - Insufficient margin-related content"
            
            return {
                'is_interesting': is_interesting,
                'reason': reason,
                'score': relevance_score,
                'details': matched_details,
                'commodities': mentioned_commodities,
                'context': context_data,
                'title_preview': title_preview
            }
            
        except Exception as e:
            print(f"⚠️ Error in interest detection: {e}")
            return {
                'is_interesting': False,
                'reason': f'Detection error: {e}',
                'score': 0,
                'details': [],
                'commodities': []
            }

class LLMEnhancedSHFEScraper:
    """Enhanced SHFE scraper with improved extraction logic and incremental batching"""
    def __init__(self, start_date: str, gemini_api_key: str, output_dir: str):
        self.start_date_str = start_date
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        self.today = date.today()
        self.base_url = "https://www.shfe.com.cn/publicnotice/notice/"
        self.driver = None
        self.wait = None
        
        # Configuration
        self.output_dir = output_dir
        self.dataset_name = "SHFEMR"
        self.csv_output = os.path.join(self.output_dir, f"shfe_margin_data_enhanced_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        
        # BATCHING CONFIGURATION
        self.batch_size = 10  # Save every 10 processed notices
        self.current_batch = []
        self.total_saved_entries = 0
        self.batch_count = 0
        
        # Initialize components
        self.data_exporter = SHFEDataExporter(self.dataset_name, self.output_dir)
        self.commodity_extractor = SHFECommodityExtractor()
        self.interest_detector = EnhancedMarginInterestDetector()
        self.extracted_data = []
        
        # Initialize Gemini parser with enhanced logic
        if gemini_api_key:
            try:
                self.gemini_parser = EnhancedGeminiContentParser(gemini_api_key)
                print("🤖 Enhanced Gemini content parser initialized")
            except Exception as e:
                print(f"⚠️ Gemini initialization failed: {e}")
                self.gemini_parser = None
        else:
            print("⚠️ Gemini API key not provided. Enhanced parsing will be disabled.")
            self.gemini_parser = None
    
    def setup_csv(self):
        """Initialize CSV file with headers"""
        os.makedirs(self.output_dir, exist_ok=True)
        with open(self.csv_output, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                'Date', 'Title', 'URL', 'Commodity', 'Hedging_Percentage', 
                'Speculative_Percentage', 'Effective_Date', 'Adjustment_Type',
                'Source_Sentence', 'Parsing_Method', 'Confidence', 'Scraped_At',
                'Interest_Score', 'Interest_Details', 'Detected_Commodities',
                'Batch_Number'
            ])
    
    def save_batch_to_csv(self, force_save=False):
        """Save current batch to CSV and update XLS files"""
        if not self.current_batch and not force_save:
            return
        
        if self.current_batch:
            self.batch_count += 1
            print(f"💾 Saving batch {self.batch_count} with {len(self.current_batch)} entries...")
            
            # Append to CSV
            with open(self.csv_output, 'a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                for entry in self.current_batch:
                    writer.writerow([
                        entry.get('notice_date', ''), entry.get('title', ''), entry.get('url', ''),
                        entry.get('commodity', ''), entry.get('hedging_percentage', ''),
                        entry.get('speculative_percentage', ''), entry.get('effective_date', ''),
                        entry.get('adjustment_type', ''), entry.get('source_sentence', ''),
                        entry.get('parsing_method', ''), entry.get('confidence', ''),
                        entry.get('scraped_at', ''), entry.get('interest_score', ''),
                        entry.get('interest_details', ''), entry.get('detected_commodities', ''),
                        self.batch_count
                    ])
            
            # Add to total data
            self.extracted_data.extend(self.current_batch)
            self.total_saved_entries += len(self.current_batch)
            
            # Create/update incremental XLS files
            if self.total_saved_entries > 0:
                try:
                    latest_date = max(entry['scraped_at'] for entry in self.extracted_data)
                    release_date = datetime.fromisoformat(latest_date.replace('T', ' ').split('.')[0]).strftime("%Y-%m-%d")
                    
                    # Create incremental XLS files
                    data_path, meta_path = self.data_exporter.create_xls_files(self.extracted_data, release_date)
                    print(f"📊 Updated XLS files with {self.total_saved_entries} total entries")
                except Exception as e:
                    print(f"⚠️ Error updating XLS files: {e}")
            
            # Clear current batch
            self.current_batch = []
            print(f"✅ Batch {self.batch_count} saved. Total entries: {self.total_saved_entries}")
    
    def add_entry_to_batch(self, entry):
        """Add entry to current batch and save if batch is full"""
        entry['batch_number'] = self.batch_count + 1
        self.current_batch.append(entry)
        
        # Save batch if it's full
        if len(self.current_batch) >= self.batch_size:
            self.save_batch_to_csv()
    
    def scrape_notice_content(self, notice_url: str, title: str, notice_date: date, interest_info: dict = None) -> int:
        """Enhanced notice scraping with improved Gemini parsing"""
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
            
            if not self.gemini_parser:
                print("⚠️ Enhanced Gemini parser not available")
                return 0
            
            # Pre-filter: Quick check if it's likely a margin notice
            if not self.quick_margin_check_enhanced(clean_text, interest_info):
                print("⚡ Enhanced quick filter: Not a margin notice (skipping Gemini)")
                return 0
            
            print("🤖 Parsing content with Enhanced Gemini Logic...")
            try:
                gemini_result = self.gemini_parser.parse_margin_notice(clean_text, title)
            except Exception as e:
                print(f"⚠️ Enhanced Gemini parsing error: {e}")
                return 0
            
            if not gemini_result.get('is_margin_notice', False):
                print("📄 Not a margin ratio adjustment notice")
                return 0
            
            # Process Gemini results with enhanced validation
            saved_count = 0
            for date_entry in gemini_result.get('effective_dates', []):
                effective_date = date_entry.get('date', '')
                for commodity_data in date_entry.get('commodities', []):
                    commodity = commodity_data.get('commodity', 'Unknown')
                    
                    # Enhanced validation
                    hedging_pct = commodity_data.get('hedging_percentage', 0)
                    speculative_pct = commodity_data.get('speculative_percentage', 0)
                    
                    # Skip if percentages exceed validation limit
                    if hedging_pct > 20 or speculative_pct > 20:
                        print(f"⚠️ Skipping {commodity}: percentages exceed 20% limit")
                        continue
                    
                    entry = {
                        'notice_date': notice_date.strftime("%Y-%m-%d"),
                        'title': title,
                        'url': notice_url,
                        'commodity': commodity,
                        'hedging_percentage': hedging_pct,
                        'speculative_percentage': speculative_pct,
                        'effective_date': effective_date,
                        'adjustment_type': commodity_data.get('adjustment_type', 'adjusted_to'),
                        'source_sentence': commodity_data.get('source_sentence', '')[:200],
                        'parsing_method': 'Gemini_Enhanced',
                        'confidence': gemini_result.get('parsing_confidence', 'medium'),
                        'scraped_at': datetime.now().isoformat(),
                        'interest_score': interest_info.get('score', 0) if interest_info else 0,
                        'interest_details': '; '.join(interest_info.get('details', [])) if interest_info else '',
                        'detected_commodities': '; '.join(interest_info.get('commodities', [])) if interest_info else '',
                        'entry_type': 'margin_data'  # Added for filtering
                    }
                    
                    # Add to batch instead of direct CSV
                    self.add_entry_to_batch(entry)
                    saved_count += 1
            
            if saved_count > 0:
                print(f"💾 Added {saved_count} margin entries to batch")
            
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
    
    def is_likely_margin_notice_enhanced(self, notice_element) -> dict:
        """Enhanced margin-specific interest detection"""
        try:
            interest_result = self.interest_detector.is_notice_interesting(notice_element)
            return interest_result
        except Exception as e:
            print(f"⚠️ Error in enhanced interest detection: {e}")
            return {
                'is_interesting': False,
                'reason': f'Detection error: {e}',
                'score': 0,
                'details': [],
                'commodities': []
            }
    
    def quick_margin_check_enhanced(self, content: str, interest_info: dict = None) -> bool:
        """Enhanced quick check using interest detection context"""
        margin_indicators = [
            'margin ratio', 'trading margin', '保证金', '交易保证金',
            'hedging', 'speculative', '套期保值', '投机',
            'price limit', '价格限额', 'adjusted to', '调整'
        ]
        
        content_lower = content.lower()
        matches = sum(1 for indicator in margin_indicators if indicator in content_lower)
        
        # Lower threshold if we have high interest score
        required_matches = 2 if (interest_info and interest_info.get('score', 0) > 15) else 3
        is_likely = matches >= required_matches
        
        if not is_likely:
            print(f"⚡ Enhanced quick filter: Only {matches}/{required_matches}+ margin indicators found")
        
        return is_likely
    
    def process_notices_on_page_safe(self, page_num: int) -> Tuple[int, int, int]:
        """Process notices with enhanced error handling and margin focus"""
        processed_count = 0
        extracted_count = 0
        enhanced_filter_savings = 0
        
        try:
            # Wait for page content with multiple fallback strategies
            content_found = False
            selectors_to_try = [
                ".detail_content",
                ".table_item_info",
                ".notice_item",
                ".list_item",
                "[class*='item']"
            ]
            
            for selector in selectors_to_try:
                try:
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    content_found = True
                    break
                except TimeoutException:
                    continue
            
            if not content_found:
                print(f"❌ Could not find any notice content on page {page_num}")
                return 0, 0, 0
            
            # Find notice items with multiple strategies
            notice_items = []
            selectors_to_try = [
                ".table_item_info",
                ".notice_item", 
                ".list_item",
                "[class='item_info']",
                "[class='notice']"
            ]
            
            for selector in selectors_to_try:
                try:
                    notice_items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if notice_items:
                        break
                except:
                    continue
            
            if not notice_items:
                print(f"⚠️ No notice items found on page {page_num}")
                return 0, 0, 0
            
            print(f"📋 Found {len(notice_items)} notices on page {page_num}")
            
            page_filtered_count = 0
            for idx, item in enumerate(notice_items):
                try:
                    # Extract date with error handling
                    notice_date = None
                    try:
                        date_element = item.find_element(By.CSS_SELECTOR, ".info_item_date")
                        date_text = date_element.text.strip()
                        notice_date = self.parse_date(date_text)
                    except:
                        # Try alternate date extraction
                        element_text = item.text
                        date_match = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', element_text)
                        if date_match:
                            try:
                                notice_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").date()
                                date_text = date_match.group(1)
                            except:
                                continue
                        else:
                            print(f"⚠️ Could not extract date from notice {idx + 1}")
                            continue
                    
                    if not self.is_date_in_range(notice_date):
                        continue
                    
                    # Enhanced MARGIN-FOCUSED interest detection
                    interest_result = self.is_likely_margin_notice_enhanced(item)
                    if not interest_result['is_interesting']:
                        page_filtered_count += 1
                        enhanced_filter_savings += 1
                        continue
                    
                    # Extract title and URL
                    try:
                        title_element = item.find_element(By.CSS_SELECTOR, ".info_item_title a")
                        title = title_element.get_attribute("title") or title_element.text
                        relative_url = title_element.get_attribute("href")
                    except:
                        try:
                            # Fallback title extraction
                            title_element = item.find_element(By.TAG_NAME, "a")
                            title = title_element.text
                            relative_url = title_element.get_attribute("href")
                        except:
                            print(f"⚠️ Could not extract title/URL from notice {idx + 1}")
                            continue
                    
                    # Build full URL
                    if relative_url.startswith("./"):
                        full_url = self.base_url + relative_url[2:]
                    elif relative_url.startswith("/"):
                        full_url = "https://www.shfe.com.cn" + relative_url
                    else:
                        full_url = relative_url
                    
                    processed_count += 1
                    print(f"\n🎯 Processing ({processed_count}) on Page {page_num}: {title[:80]}... ({date_text})")
                    print(f"🧠 Margin Interest Score: {interest_result['score']:.1f} - {interest_result['reason']}")
                    
                    try:
                        entry_count = self.scrape_notice_content(full_url, title, notice_date, interest_result)
                        extracted_count += entry_count
                        
                        # Save batch periodically during processing
                        if self.total_saved_entries > 0 and self.total_saved_entries % 50 == 0:
                            print(f"🔄 Checkpoint: {self.total_saved_entries} entries saved so far...")
                    except Exception as e:
                        print(f"⚠️ Error processing notice content: {e}")
                        continue
                        
                except Exception as e:
                    print(f"❌ Error processing notice {idx + 1}: {e}")
                    continue
            
            # Save any remaining batch items for this page
            if len(self.current_batch) > 0:
                print(f"💾 Saving remaining {len(self.current_batch)} entries from page {page_num}")
                self.save_batch_to_csv()
            
            print(f"📄 Page {page_num} Summary: {processed_count} margin notices processed, {extracted_count} entries extracted")
            if page_filtered_count > 0:
                print(f"🚫 Filtered out {page_filtered_count} non-margin notices")
                
        except Exception as e:
            print(f"❌ Critical error on page {page_num}: {e}")
            # Save any data we have so far
            if len(self.current_batch) > 0:
                print("💾 Emergency save of current batch due to error...")
                self.save_batch_to_csv()
        
        return processed_count, extracted_count, enhanced_filter_savings
    
    def run_scraper(self):
        """Main execution with enhanced margin focus and crash recovery"""
        print("🚀 Starting ENHANCED SHFE Margin Scraper with Improved Extraction Logic")
        print(f"📊 Dataset: {self.dataset_name}")
        print(f"📅 Date range: {self.start_date_str} to {self.today}")
        print(f"🤖 Enhanced Gemini content parsing: {'Enabled' if self.gemini_parser else 'Disabled'}")
        print(f"💾 Batch size: {self.batch_size} entries")
        print(f"🎯 STRATEGY: Focus on margin ratio adjustments with enhanced extraction logic")
        print(f"🛡️ CRASH RECOVERY: Data saved incrementally, no loss on crashes")
        print(f"📏 Enhanced filtering: Higher precision, margin-specific detection")
        print()
        
        try:
            self.setup_driver()
            self.setup_csv()
            
            if not self.load_initial_page_with_retry():
                print("❌ Could not load main page. Exiting.")
                return None
            
            page_count = 0
            total_processed = 0
            total_extracted = 0
            total_filter_savings = 0
            consecutive_empty_pages = 0
            
            while True:
                page_count += 1
                print(f"\n📄 Processing page {page_count}")
                
                try:
                    processed, extracted, filter_savings = self.process_notices_on_page_safe(page_count)
                    total_processed += processed
                    total_extracted += extracted
                    total_filter_savings += filter_savings
                    
                    if processed == 0: 
                        consecutive_empty_pages += 1
                    else: 
                        consecutive_empty_pages = 0
                    
                    # Conservative termination for margin-focused scraping
                    if consecutive_empty_pages > 3 or page_count > 15:
                        print(f"🛑 Stopping: {consecutive_empty_pages} consecutive empty pages or max pages reached")
                        break
                    
                    if not self.navigate_to_next_page():
                        print("🛑 No more pages to process")
                        break
                        
                except Exception as e:
                    print(f"❌ Error on page {page_count}: {e}")
                    print("💾 Saving current progress before continuing...")
                    self.save_batch_to_csv(force_save=True)
                    
                    # Try to continue or break based on error type
                    if "session" in str(e).lower() or "disconnect" in str(e).lower():
                        print("🔄 Browser session lost, stopping here...")
                        break
                    else:
                        print("🔄 Attempting to continue...")
                        continue
            
            # Final save
            print("\n💾 Final save of all remaining data...")
            self.save_batch_to_csv(force_save=True)
            
            print(f"\n🎉 Enhanced margin scraping completed!")
            print(f"📊 PROCESSING SUMMARY:")
            print(f"   📄 Pages processed: {page_count}")
            print(f"   🎯 Margin notices processed: {total_processed}")
            print(f"   💾 Total entries saved: {self.total_saved_entries}")
            print(f"   🚫 Non-margin notices filtered: {total_filter_savings}")
            print(f"   📦 Batches saved: {self.batch_count}")
            
            # Create final ZIP only at the very end
            if self.total_saved_entries > 0:
                print(f"\n📦 Creating final ZIP archive...")
                try:
                    latest_date = max(entry['scraped_at'] for entry in self.extracted_data)
                    release_date = datetime.fromisoformat(latest_date.replace('T', ' ').split('.')[0]).strftime("%Y-%m-%d")
                    
                    data_path, meta_path = self.data_exporter.create_xls_files(self.extracted_data, release_date)
                    zip_path = self.data_exporter.create_zip_archive(data_path, meta_path)
                    
                    # Enhanced summary stats
                    unique_commodities = len(set(entry['commodity'] for entry in self.extracted_data))
                    unique_dates = len(set(entry['effective_date'] for entry in self.extracted_data))
                    adjustment_types = {}
                    for entry in self.extracted_data:
                        adj_type = entry['adjustment_type']
                        adjustment_types[adj_type] = adjustment_types.get(adj_type, 0) + 1
                    
                    print(f"✅ SUCCESS! Final output:")
                    print(f"   📄 CSV: {self.csv_output}")
                    print(f"   📦 ZIP: {zip_path}")
                    print(f"   💾 Total margin entries: {self.total_saved_entries}")
                    print(f"   🎯 Unique commodities: {unique_commodities}")
                    print(f"   📅 Effective dates: {unique_dates}")
                    print(f"   📋 Adjustment types: {adjustment_types}")
                    print(f"   🤖 Parsing method: Gemini_Enhanced")
                    
                    return zip_path
                    
                except Exception as e:
                    print(f"⚠️ Error creating final ZIP: {e}")
                    print(f"💾 Data is still saved in CSV: {self.csv_output}")
                    return self.csv_output
            else:
                print("💡 No margin adjustment notices found in the specified date range.")
                print("   Enhanced suggestions:")
                print("   - Try expanding the date range (e.g., start from '2024-12-01')")
                print("   - Look for holiday periods when margin adjustments are common")
                print("   - Check recent market volatility periods")
                print("   - Verify the SHFE website is accessible")
                return None
                
        except Exception as e:
            print(f"❌ Critical scraping error: {e}")
            # Final emergency save
            self.save_batch_to_csv(force_save=True)
            if self.total_saved_entries > 0:
                print(f"💾 Emergency save completed. Data preserved in: {self.csv_output}")
                return self.csv_output
            return None
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
    
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
            self.driver.set_page_load_timeout(20)
            self.driver.implicitly_wait(5)
            self.wait = WebDriverWait(self.driver, 10)
            print("✅ Chrome driver initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize Chrome driver: {e}")
            raise
    
    def extract_clean_text(self, page_source: str) -> str:
        """Extract clean text from page source"""
        clean_content = re.sub(r'<script.*?</script>', '', page_source, flags=re.DOTALL)
        clean_content = re.sub(r'<style.*?</style>', '', clean_content, flags=re.DOTALL)
        clean_content = re.sub(r'<[^>]+>', ' ', clean_content)
        clean_content = re.sub(r'\s+', ' ', clean_content)
        return clean_content.strip()
    
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
            next_selectors = [".btn-next:not([disabled])", ".el-pagination__next:not(.is-disabled)", ".pagination-next:not(.disabled)"]
            next_button = None
            
            for selector in next_selectors:
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue
            
            if not next_button:
                print("➡️ No next button found")
                return False
            
            next_button.click()
            time.sleep(2)
            
            try:
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                return True
            except TimeoutException:
                print("⏰ Timeout after clicking next page")
                return False
        except Exception as e:
            print(f"❌ Error navigating to next page: {e}")
            return False
    
    def load_initial_page_with_retry(self) -> bool:
        """Load the main page with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"🌐 Loading main page (attempt {attempt + 1}/{max_retries})...")
                print(f"🔗 URL: {self.base_url}")
                self.driver.get(self.base_url)
                
                try:
                    self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                    current_url = self.driver.current_url
                    print(f"✅ Main page loaded successfully")
                    print(f"🔗 Actual URL: {current_url}")
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
    
    def export_final_data(self) -> str:
        """Export final data in runbook format"""
        if not self.extracted_data:
            return ""
        
        latest_date = max(entry['scraped_at'] for entry in self.extracted_data)
        release_date = datetime.fromisoformat(latest_date.replace('T', ' ').split('.')[0]).strftime("%Y-%m-%d")
        
        data_path, meta_path = self.data_exporter.create_xls_files(self.extracted_data, release_date)
        zip_path = self.data_exporter.create_zip_archive(data_path, meta_path)
        
        return zip_path

# ==================== MAIN EXECUTION ====================
def main(start_date=None, gemini_api_key=None, enhanced_parsing=True):
    """Main execution function optimized for GCP Cloud Run deployment"""
    print("🏗️ Initializing Enhanced SHFE Margin Scraper...")
    print("🎯 Focus: Margin ratio adjustments with improved extraction logic")
    print("🤖 AI: Enhanced Gemini parsing with multi-commodity support")
    print("💾 Safety: Incremental batching with crash recovery")
    print("☁️ Environment: Google Cloud Platform")
    print()
    
    # Configuration for GCP deployment
    import os
    
    # Use environment variables or parameters for GCP deployment
    START_DATE = start_date if start_date else os.getenv('START_DATE', "2025-01-10")
    DATASET_NAME = "SHFEMR"
    OUTPUT_DIR = os.getenv('OUTPUT_DIR', "shfe_output")
    GEMINI_API_KEY = gemini_api_key if gemini_api_key else os.getenv('GEMINI_API_KEY', "your-gemini-api-key-here")
    ENHANCED_PARSING = enhanced_parsing
    
    print(f"📅 Start date: {START_DATE}")
    print(f"🔑 API key status: {'Configured' if GEMINI_API_KEY != 'your-gemini-api-key-here' else 'Not set'}")
    print(f"🚀 Enhanced parsing: {'Enabled' if ENHANCED_PARSING else 'Standard'}")
    print(f"📁 Output directory: {OUTPUT_DIR}")
    print()
    
    # Validate configuration for GCP
    if GEMINI_API_KEY == "your-gemini-api-key-here":
        error_msg = "❌ Gemini API key not configured. Set GEMINI_API_KEY environment variable."
        print(error_msg)
        return {"error": error_msg, "status": "failed"}
    
    if not GEMINI_AVAILABLE:
        error_msg = "❌ Required dependencies not available. Install google-generativeai, xlwt, selenium"
        print(error_msg)
        return {"error": error_msg, "status": "failed"}
    
    print("📋 ENHANCED EXTRACTION FEATURES:")
    print("✅ Multiple commodities per sentence extraction")
    print("✅ Enhanced commodity name standardization")
    print("✅ Improved validation rules (≤20% percentages)")
    print("✅ Better date extraction patterns")
    print("✅ Margin-focused filtering with high precision")
    print("✅ Incremental batching for crash recovery")
    print("✅ Enhanced Gemini parsing logic")
    print()
    
    try:
        # Initialize and run scraper
        scraper = LLMEnhancedSHFEScraper(
            start_date=START_DATE,
            gemini_api_key=GEMINI_API_KEY,
            output_dir=OUTPUT_DIR
        )
        
        print(f"🚀 Starting enhanced scraping process...")
        print(f"📅 Date range: {START_DATE} to today")
        print(f"📁 Output directory: {OUTPUT_DIR}")
        print()
        
        result_zip = scraper.run_scraper()
        
        if result_zip:
            print(f"\n🎉 ENHANCED SCRAPING COMPLETED SUCCESSFULLY!")
            print(f"📦 Final output: {result_zip}")
            
            # Return structured response for GCP
            return {
                "status": "success",
                "message": "Enhanced scraping completed successfully",
                "output_file": result_zip,
                "start_date": START_DATE,
                "total_entries": scraper.total_saved_entries,
                "batches_processed": scraper.batch_count,
                "features": {
                    "enhanced_parsing": ENHANCED_PARSING,
                    "incremental_batching": True,
                    "crash_recovery": True,
                    "multi_commodity_extraction": True
                },
                "files_created": {
                    "csv": scraper.csv_output,
                    "zip": result_zip
                }
            }
        else:
            warning_msg = f"No margin adjustment notices found in date range {START_DATE} to today"
            print(f"\n💡 {warning_msg}")
            print("📝 Suggestions for better results:")
            print("   • Try expanding the date range (e.g., start from '2024-12-01')")
            print("   • Look for holiday periods when margin adjustments are common")
            print("   • Check recent market volatility periods")
            
            return {
                "status": "no_data",
                "message": warning_msg,
                "start_date": START_DATE,
                "suggestions": [
                    "Try expanding the date range",
                    "Look for holiday periods when margin adjustments are common",
                    "Check recent market volatility periods"
                ]
            }
            
    except KeyboardInterrupt:
        error_msg = "Scraping interrupted by user"
        print(f"\n⚠️ {error_msg}")
        return {"error": error_msg, "status": "interrupted"}
    except Exception as e:
        error_msg = f"Critical error during execution: {str(e)}"
        print(f"\n❌ {error_msg}")
        print("🔧 Troubleshooting suggestions:")
        print("   • Check internet connection stability")
        print("   • Verify Chrome browser is installed and updated")
        print("   • Ensure Gemini API key is valid and has quota")
        print("   • Try running with a different date range")
        print("   • Check if SHFE website is accessible manually")
        
        return {
            "error": error_msg,
            "status": "failed",
            "troubleshooting": [
                "Check internet connection stability",
                "Verify Chrome browser is installed and updated", 
                "Ensure Gemini API key is valid and has quota",
                "Try running with a different date range",
                "Check if SHFE website is accessible manually"
            ]
        }

# ==================== FLASK/FASTAPI WEB SERVICE ====================
def create_web_service():
    """Create Flask web service for GCP Cloud Run deployment"""
    try:
        from flask import Flask, request, jsonify
        FLASK_AVAILABLE = True
    except ImportError:
        print("⚠️ Flask not available. Install with: pip install flask")
        FLASK_AVAILABLE = False
        return None
    
    app = Flask(__name__)
    
    @app.route('/shfe/run', methods=['POST'])
    def run_shfe_scraper():
        """HTTP endpoint for running SHFE scraper"""
        try:
            # Parse JSON request
            data = request.get_json()
            if not data:
                return jsonify({
                    "error": "No JSON data provided",
                    "status": "failed"
                }), 400
            
            # Extract parameters
            start_date = data.get('start_date')
            enhanced_parsing = data.get('enhanced_parsing', True)
            
            # Validate start_date format
            if start_date:
                try:
                    datetime.strptime(start_date, "%Y-%m-%d")
                except ValueError:
                    return jsonify({
                        "error": "Invalid start_date format. Use YYYY-MM-DD",
                        "status": "failed"
                    }), 400
            
            print(f"🌐 HTTP Request received:")
            print(f"   start_date: {start_date}")
            print(f"   enhanced_parsing: {enhanced_parsing}")
            
            # Run scraper
            result = main(
                start_date=start_date,
                enhanced_parsing=enhanced_parsing
            )
            
            # Return appropriate HTTP status
            if result.get('status') == 'success':
                return jsonify(result), 200
            elif result.get('status') == 'no_data':
                return jsonify(result), 200  # Still successful, just no data
            else:
                return jsonify(result), 500
                
        except Exception as e:
            error_response = {
                "error": f"Internal server error: {str(e)}",
                "status": "failed"
            }
            return jsonify(error_response), 500
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint for GCP"""
        return jsonify({
            "status": "healthy",
            "service": "Enhanced SHFE Margin Scraper",
            "version": "2.0",
            "features": [
                "Enhanced Gemini parsing",
                "Multi-commodity extraction",
                "Incremental batching",
                "Crash recovery"
            ]
        }), 200
    
    @app.route('/config', methods=['GET'])
    def get_config():
        """Configuration endpoint"""
        import os
        return jsonify({
            "default_start_date": "2025-01-10",
            "dataset_name": "SHFEMR",
            "output_dir": os.getenv('OUTPUT_DIR', 'shfe_output'),
            "gemini_configured": os.getenv('GEMINI_API_KEY') is not None,
            "enhanced_parsing_available": True,
            "supported_parameters": {
                "start_date": "YYYY-MM-DD format",
                "enhanced_parsing": "boolean (default: true)"
            }
        }), 200
    
    return app

def test_configuration():
    """Test configuration and dependencies"""
    print("🔧 Testing Enhanced SHFE Scraper Configuration...")
    
    # Test imports
    missing_deps = []
    if not GEMINI_AVAILABLE:
        missing_deps.append("google-generativeai")
    
    try:
        import xlwt
    except ImportError:
        missing_deps.append("xlwt")
    
    try:
        from selenium import webdriver
    except ImportError:
        missing_deps.append("selenium")
    
    if missing_deps:
        print(f"❌ Missing dependencies: {', '.join(missing_deps)}")
        print(f"   Install with: pip install {' '.join(missing_deps)}")
        return False
    
    # Test Chrome driver
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)
        driver.quit()
        print("✅ Chrome driver test successful")
    except Exception as e:
        print(f"❌ Chrome driver test failed: {e}")
        print("   Please ensure Chrome and chromedriver are installed")
        return False
    
    # Test API key format (basic validation)
    test_api_key = "your-gemini-api-key-here"
    if test_api_key == "your-gemini-api-key-here":
        print("⚠️ Please set your actual Gemini API key")
        print("   Get one from: https://makersuite.google.com/app/apikey")
    else:
        print("✅ API key format looks valid")
    
    print("✅ Configuration test completed")
    return True

def usage_examples():
    """Show usage examples for different scenarios"""
    print("📖 ENHANCED SHFE SCRAPER USAGE EXAMPLES:")
    print()
    print("1️⃣ HTTP POST REQUEST:")
    print("   curl -X POST -H 'Content-Type: application/json' \\")
    print("        -d '{\"start_date\": \"2025-01-10\", \"enhanced_parsing\": true}' \\")
    print("        https://shfe-scraper-of2rqcfxqa-uc.a.run.app/shfe/run")
    print()
    print("2️⃣ DIFFERENT DATE RANGES:")
    print("   # Holiday period")
    print("   -d '{\"start_date\": \"2024-12-01\", \"enhanced_parsing\": true}'")
    print("   # New year period")
    print("   -d '{\"start_date\": \"2025-01-01\", \"enhanced_parsing\": true}'")
    print("   # Recent data")
    print("   -d '{\"start_date\": \"2025-01-20\", \"enhanced_parsing\": true}'")
    print()
    print("3️⃣ HEALTH CHECK:")
    print("   curl https://shfe-scraper-of2rqcfxqa-uc.a.run.app/health")
    print()
    print("4️⃣ CONFIGURATION INFO:")
    print("   curl https://shfe-scraper-of2rqcfxqa-uc.a.run.app/config")
    print()
    print("5️⃣ RESPONSE FORMAT:")
    print("   Success: {\"status\": \"success\", \"output_file\": \"...\", \"total_entries\": 42}")
    print("   No data: {\"status\": \"no_data\", \"message\": \"...\", \"suggestions\": [...]}")
    print("   Error: {\"status\": \"failed\", \"error\": \"...\", \"troubleshooting\": [...]}")
    print()
    print("6️⃣ ENVIRONMENT VARIABLES (for deployment):")
    print("   GEMINI_API_KEY=your-gemini-api-key")
    print("   OUTPUT_DIR=/tmp/shfe_output")
    print("   START_DATE=2025-01-10")

if __name__ == "__main__":
    import sys
    
    # Configuration
    START_DATE = "2025-01-10"
    DATASET_NAME = "SHFEMR"
    OUTPUT_DIR = "shfe_output"
    GEMINI_API_KEY = "your-gemini-api-key-here"  # Replace with your API key
    
    # Show help if requested
    if '--help' in sys.argv or '-h' in sys.argv:
        print("🔧 ENHANCED SHFE MARGIN SCRAPER - GCP DEPLOYMENT")
        print("================================================")
        usage_examples()
        sys.exit(0)
    
    # For local development/testing
    if '--local' in sys.argv:
        print("🧪 Running in local development mode...")
        if test_configuration():
            # Validate configuration
            if GEMINI_API_KEY == "your-gemini-api-key-here":
                print("❌ Please set your actual Gemini API key in the GEMINI_API_KEY variable")
                print("   You can get an API key from: https://makersuite.google.com/app/apikey")
                sys.exit(1)
            
            if not GEMINI_AVAILABLE:
                print("❌ Please install required dependencies:")
                print("   pip install google-generativeai xlwt selenium")
                sys.exit(1)
            
            print("📋 ENHANCED EXTRACTION FEATURES:")
            print("✅ Multiple commodities per sentence extraction")
            print("✅ Enhanced commodity name standardization")
            print("✅ Improved validation rules (≤20% percentages)")
            print("✅ Better date extraction patterns")
            print("✅ Margin-focused filtering with high precision")
            print("✅ Incremental batching for crash recovery")
            print("✅ Enhanced Gemini parsing logic")
            print()
            
            try:
                # Initialize and run scraper
                scraper = LLMEnhancedSHFEScraper(
                    start_date=START_DATE,
                    gemini_api_key=GEMINI_API_KEY,
                    output_dir=OUTPUT_DIR
                )
                
                print(f"🚀 Starting enhanced scraping process...")
                print(f"📅 Date range: {START_DATE} to today")
                print(f"📁 Output directory: {OUTPUT_DIR}")
                print()
                
                result_zip = scraper.run_scraper()
                
                if result_zip:
                    print(f"\n🎉 ENHANCED SCRAPING COMPLETED SUCCESSFULLY!")
                    print(f"📦 Final output: {result_zip}")
                    print("\n🎯 Key improvements achieved:")
                    print("   • Multiple commodities per sentence extraction")
                    print("   • Enhanced commodity name standardization") 
                    print("   • Improved validation rules (≤20% percentages)")
                    print("   • Better date extraction patterns")
                    print("   • Margin-focused filtering with higher precision")
                    print("   • Incremental batching for crash recovery")
                    print("   • Enhanced Gemini parsing logic")
                    print("\n✅ Ready for SFTP upload to data repository")
                else:
                    print(f"\n💡 No margin adjustment notices found in date range")
                    print("📝 Suggestions for better results:")
                    print("   • Try expanding the date range (e.g., start from '2024-12-01')")
                    print("   • Look for holiday periods when margin adjustments are common")
                    print("   • Check recent market volatility periods")
                    print("   • Verify the SHFE website is accessible")
                    print("   • Consider checking Shanghai International Energy Exchange notices")
                    
            except KeyboardInterrupt:
                print("\n⚠️ Scraping interrupted by user")
                print("💾 Any processed data should be saved in incremental files")
            except Exception as e:
                print(f"\n❌ Critical error during execution: {e}")
                print("🔧 Troubleshooting suggestions:")
                print("   • Check internet connection stability")
                print("   • Verify Chrome browser is installed and updated")
                print("   • Ensure Gemini API key is valid and has quota")
                print("   • Try running with a different date range")
                print("   • Check if SHFE website is accessible manually")
                print("   • Review Chrome driver compatibility")
        else:
            print("\n❌ Configuration test failed. Please fix issues before running.")
    
    # For GCP Cloud Run deployment
    elif '--web' in sys.argv or len(sys.argv) == 1:
        print("🌐 Starting web service for GCP Cloud Run...")
        app = create_web_service()
        if app:
            # Use environment variables for GCP
            import os
            port = int(os.environ.get('PORT', 8080))
            app.run(host='0.0.0.0', port=port, debug=False)
        else:
            print("❌ Could not create web service. Install Flask: pip install flask")
    
    else:
        usage_examples()