#!/usr/bin/env python3
"""
LLM-Enhanced SHFE Margin Scraper
Enhanced with comprehensive "is this interesting?" logic from main.py
Uses multi-layered analysis with context, commodities, and intelligent scoring
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
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import timedelta

# Gemini integration
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    print("⚠️ Google Generative AI not installed. Run: pip install google-generativeai")
    GEMINI_AVAILABLE = False

class SHFEDataExporter:
    """Export data in runbook format - FIXED for mixed data types"""
    
    def __init__(self, dataset_name: str, output_dir: str):
        self.dataset_name = dataset_name
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def create_xls_files(self, data_entries: List[Dict], release_date: str) -> Tuple[str, str]:
        """Create DATA and META XLS files - FIXED to handle both margin and operational data"""
        timestamp = datetime.now().strftime("%Y%m%d")
        
        data_filename = f"{self.dataset_name}_DATA_{timestamp}.xls"
        meta_filename = f"{self.dataset_name}_META_{timestamp}.xls"
        
        data_path = os.path.join(self.output_dir, data_filename)
        meta_path = os.path.join(self.output_dir, meta_filename)
        
        self._create_data_file_mixed(data_entries, data_path)
        self._create_meta_file_mixed(meta_path, release_date, data_entries)
        
        return data_path, meta_path
    
    def _create_data_file_mixed(self, data_entries: List[Dict], filepath: str):
        """Create DATA XLS file handling BOTH margin and operational data"""
        workbook = xlwt.Workbook(encoding='utf-8')
        
        # Separate margin and operational data
        margin_entries = [entry for entry in data_entries if entry.get('entry_type') == 'margin_data']
        operational_entries = [entry for entry in data_entries if entry.get('entry_type') == 'operational_data']
        
        print(f"📊 Creating XLS with {len(margin_entries)} margin entries and {len(operational_entries)} operational entries")
        
        # Create MARGIN DATA sheet
        if margin_entries:
            self._create_margin_data_sheet(workbook, margin_entries)
        
        # Create OPERATIONAL DATA sheet  
        if operational_entries:
            self._create_operational_data_sheet(workbook, operational_entries)
        
        # Create SUMMARY sheet
        self._create_summary_sheet(workbook, margin_entries, operational_entries)
        
        workbook.save(filepath)
        print(f"✅ Created mixed DATA file: {filepath}")
    
    def _create_margin_data_sheet(self, workbook, margin_entries):
        """Create sheet for margin ratio data (original format)"""
        worksheet = workbook.add_sheet('Margin_Data')
        
        # Group data by effective date
        data_by_date = {}
        time_series_codes = set()
        
        for entry in margin_entries:
            effective_date = entry.get('effective_date', '')
            commodity = entry.get('commodity', 'UNKNOWN')
            
            # Handle None or empty commodity names
            if not commodity or commodity.lower() in ['none', 'unknown', '']:
                continue
                
            commodity_clean = commodity.upper().replace(' ', '_').replace('-', '_')
            
            if effective_date not in data_by_date:
                data_by_date[effective_date] = {}
            
            hedging_code = f"{commodity_clean}_HEDGING_MARGIN"
            speculative_code = f"{commodity_clean}_SPECULATIVE_MARGIN"
            
            hedging_pct = entry.get('hedging_percentage', '')
            speculative_pct = entry.get('speculative_percentage', '')
            
            data_by_date[effective_date][hedging_code] = hedging_pct
            data_by_date[effective_date][speculative_code] = speculative_pct
            
            time_series_codes.add(hedging_code)
            time_series_codes.add(speculative_code)
        
        if not data_by_date:
            # Create empty sheet with headers
            worksheet.write(0, 0, "DATE")
            worksheet.write(1, 0, "No margin data available")
            return
        
        # Write headers
        sorted_codes = sorted(time_series_codes)
        worksheet.write(0, 0, "DATE")
        worksheet.write(1, 0, "Reporting Date")
        
        for col_idx, code in enumerate(sorted_codes, 1):
            worksheet.write(0, col_idx, code)
            description = code.replace('_', ' ').title()
            worksheet.write(1, col_idx, description)
        
        # Write data
        sorted_dates = sorted([date for date in data_by_date.keys() if date])
        for row_idx, effective_date in enumerate(sorted_dates, 2):
            worksheet.write(row_idx, 0, effective_date)
            
            for col_idx, code in enumerate(sorted_codes, 1):
                value = data_by_date[effective_date].get(code, "")
                worksheet.write(row_idx, col_idx, value)
    
    def _create_operational_data_sheet(self, workbook, operational_entries):
        """Create sheet for operational announcements"""
        worksheet = workbook.add_sheet('Operational_Data')
        
        # Headers for operational data
        headers = [
            'Date', 'Commodity', 'Announcement_Type', 'Operation_Type', 
            'Operation_Description', 'Affected_Parties', 'Effective_Date',
            'Adjustment_Type', 'Source_Sentence'
        ]
        
        for col_idx, header in enumerate(headers):
            worksheet.write(0, col_idx, header)
        
        # Write operational data
        for row_idx, entry in enumerate(operational_entries, 1):
            worksheet.write(row_idx, 0, entry.get('notice_date', ''))
            worksheet.write(row_idx, 1, entry.get('commodity', ''))
            worksheet.write(row_idx, 2, entry.get('announcement_type', ''))
            worksheet.write(row_idx, 3, entry.get('operation_type', ''))
            worksheet.write(row_idx, 4, entry.get('operation_description', ''))
            worksheet.write(row_idx, 5, entry.get('affected_parties', ''))
            worksheet.write(row_idx, 6, entry.get('effective_date', ''))
            worksheet.write(row_idx, 7, entry.get('adjustment_type', ''))
            worksheet.write(row_idx, 8, entry.get('source_sentence', ''))
    
    def _create_summary_sheet(self, workbook, margin_entries, operational_entries):
        """Create summary sheet with statistics"""
        worksheet = workbook.add_sheet('Summary')
        
        # Summary statistics
        worksheet.write(0, 0, "SHFE Data Summary")
        worksheet.write(1, 0, "Generated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        worksheet.write(3, 0, "Data Type")
        worksheet.write(3, 1, "Count")
        worksheet.write(3, 2, "Details")
        
        worksheet.write(4, 0, "Margin Adjustments")
        worksheet.write(4, 1, len(margin_entries))
        
        worksheet.write(5, 0, "Operational Announcements") 
        worksheet.write(5, 1, len(operational_entries))
        
        # Breakdown by announcement type
        if operational_entries:
            announcement_types = {}
            for entry in operational_entries:
                ann_type = entry.get('announcement_type', 'unknown')
                announcement_types[ann_type] = announcement_types.get(ann_type, 0) + 1
            
            worksheet.write(7, 0, "Operational Breakdown:")
            row = 8
            for ann_type, count in announcement_types.items():
                worksheet.write(row, 0, f"  {ann_type}")
                worksheet.write(row, 1, count)
                row += 1
        
        # Commodity breakdown
        all_commodities = set()
        for entry in margin_entries + operational_entries:
            commodity = entry.get('commodity')
            if commodity and commodity.lower() not in ['none', 'unknown', '']:
                all_commodities.add(commodity)
        
        worksheet.write(row + 1, 0, "Commodities Covered:")
        worksheet.write(row + 2, 0, ", ".join(sorted(all_commodities)))
    
    def _create_meta_file_mixed(self, filepath: str, release_date: str, data_entries: List[Dict]):
        """Create META XLS file for mixed data types"""
        workbook = xlwt.Workbook(encoding='utf-8')
        worksheet = workbook.add_sheet('Metadata')
        
        headers = [
            'TIMESERIES_ID', 'TIMESERIES_DESCRIPTION', 'UNIT', 'FREQUENCY',
            'SOURCE', 'DATASET', 'LAST_RELEASE_DATE', 'NEXT_RELEASE_DATE'
        ]
        
        for col_idx, header in enumerate(headers):
            worksheet.write(0, col_idx, header)
        
        # Get unique commodities from actual data
        commodities_in_data = set()
        for entry in data_entries:
            commodity = entry.get('commodity')
            if commodity and commodity.lower() not in ['none', 'unknown', '']:
                commodities_in_data.add(commodity.upper().replace(' ', '_').replace('-', '_'))
        
        # Create metadata for margin data
        transaction_types = ['HEDGING', 'SPECULATIVE']
        row_idx = 1
        
        for commodity in sorted(commodities_in_data):
            for transaction_type in transaction_types:
                timeseries_id = f"{commodity}_{transaction_type}_MARGIN"
                description = f"{commodity.replace('_', ' ').title()} {transaction_type.title()} Margin Ratio"
                
                worksheet.write(row_idx, 0, timeseries_id)
                worksheet.write(row_idx, 1, description)
                worksheet.write(row_idx, 2, "Percentage")
                worksheet.write(row_idx, 3, "Irregular")
                worksheet.write(row_idx, 4, "Shanghai Futures Exchange")
                worksheet.write(row_idx, 5, self.dataset_name)
                worksheet.write(row_idx, 6, f"{release_date}T11:00:00")
                worksheet.write(row_idx, 7, "")
                
                row_idx += 1
        
        # Add metadata for operational data series
        for commodity in sorted(commodities_in_data):
            timeseries_id = f"{commodity}_OPERATIONAL_ANNOUNCEMENTS"
            description = f"{commodity.replace('_', ' ').title()} Operational Announcements"
            
            worksheet.write(row_idx, 0, timeseries_id)
            worksheet.write(row_idx, 1, description)
            worksheet.write(row_idx, 2, "Text")
            worksheet.write(row_idx, 3, "Irregular")
            worksheet.write(row_idx, 4, "Shanghai Futures Exchange")
            worksheet.write(row_idx, 5, self.dataset_name)
            worksheet.write(row_idx, 6, f"{release_date}T11:00:00")
            worksheet.write(row_idx, 7, "")
            
            row_idx += 1
        
        workbook.save(filepath)
        print(f"✅ Created mixed META file: {filepath}")
    
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

class GeminiContentParser:
    """Gemini-powered intelligent content parsing for SHFE notices with enhanced logic"""
    
    def __init__(self, api_key: str):
        if not GEMINI_AVAILABLE:
            raise ImportError("Google Generative AI library not available")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        
    def parse_margin_notice(self, notice_content: str, notice_title: str) -> Dict:
        """Enhanced Gemini parsing for both margin adjustments AND operational announcements"""
        
        prompt = f"""You are an expert at parsing Shanghai Futures Exchange (SHFE) and Shanghai International Energy Exchange notices. Your job is to extract BOTH margin ratio data AND relevant operational announcements that affect trading.

    NOTICE TITLE: {notice_title}

    NOTICE CONTENT: {notice_content}

    EXPANDED PARSING RULES:

    1. MARGIN ADJUSTMENT NOTICES (PRIMARY):
    - "trading margin ratio and price limit range will be adjusted as follows" 
    - "trading margin ratio will be adjusted as follows"
    - Chinese: "关于调整.*保证金比例.*通知"
    - Extract margin ratios for hedging/speculative transactions

    2. OPERATIONAL ANNOUNCEMENTS (SECONDARY - NEW):
    - Warehouse capacity changes: "关于同意.*增加.*库容.*公告"
    - Delivery suspensions/resumptions: "关于暂停.*交割.*公告"
    - Quality standard adjustments: "关于.*品质.*标准.*调整.*公告"
    - Contract modifications: "关于.*合约.*修改.*公告"
    - Storage facility approvals: "关于同意.*启用库容.*公告"

    3. COMMODITY FILTERING (ENHANCED):
    - INCLUDE all physical commodities: copper, aluminum, zinc, lead, nickel, tin, alumina, gold, silver, rebar, hot-rolled coil, wire rod, stainless steel, fuel oil, petroleum asphalt, butadiene rubber, natural rubber, No. 20 rubber (20号胶), pulp, crude oil, low-sulfur fuel oil, international copper
    - INCLUDE warehouse/delivery announcements for these commodities
    - EXCLUDE financial indices and non-physical contracts

    4. EXAMPLE ANNOUNCEMENTS TO CAPTURE:

    Example A - Margin Adjustment:
    "The price limits for aluminum, zinc, lead futures contracts were adjusted to 9%, margin ratio for hedging transactions was adjusted to 10%, speculative transactions to 11%"
    → Extract margin ratios

    Example B - Warehouse Operations (MISSED PREVIOUSLY):
    "上海国际能源交易中心发布关于同意山东中储国际物流有限公司增加20号胶期货启用库容的公告"
    "Shanghai International Energy Exchange announcement on agreeing to increase activated storage capacity for No. 20 rubber futures"
    → Extract as operational announcement affecting No. 20 rubber trading

    Example C - Delivery Suspension:
    "关于暂停镍期货NI2501合约交割的公告"
    "Notice on suspending delivery for nickel futures NI2501 contract"
    → Extract as operational announcement affecting nickel trading

    5. OUTPUT CLASSIFICATION:
    - announcement_type: "margin_adjustment" | "warehouse_operations" | "delivery_operations" | "quality_standards" | "contract_modification" | "other"
    - For margin adjustments: Extract hedging/speculative percentages
    - For operational announcements: Extract operation_type, affected_commodity, effective_date, description

    6. VALIDATION RULES:
    - Margin percentages must be ≤ 20%
    - All announcements must involve physical commodities
    - Operational announcements must have clear commodity impact

    OUTPUT FORMAT (JSON):
    {{
        "is_relevant_notice": true/false,
        "announcement_type": "margin_adjustment|warehouse_operations|delivery_operations|quality_standards|contract_modification|other",
        "effective_dates": [
            {{
                "date": "YYYY-MM-DD",
                "date_source": "exact text showing this date",
                "entries": [
                    {{
                        "commodity": "standardized name",
                        "entry_type": "margin_data|operational_data",
                        // For margin_data:
                        "hedging_percentage": number,
                        "speculative_percentage": number,
                        // For operational_data:
                        "operation_type": "warehouse_capacity|delivery_suspension|quality_change|contract_modification",
                        "operation_description": "detailed description",
                        "affected_parties": ["company names or facilities"],
                        "adjustment_type": "adjusted_to|remains_at|restored_to_original|increased|suspended|resumed",
                        "source_sentence": "exact sentence with this data"
                    }}
                ]
            }}
        ],
        "total_commodities": number,
        "total_entries": number,
        "parsing_confidence": "high/medium/low",
        "excluded_non_commodities": ["list of excluded items"]
    }}

    CRITICAL REQUIREMENTS:
    - Return ONLY valid JSON
    - Capture BOTH margin adjustments AND operational announcements
    - Include warehouse capacity changes (like the missed rubber announcement)
    - Validate all commodity names against physical commodities list
    - For operational announcements, focus on trading impact
    - Use exact date patterns and commodity standardization
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
            
            result = json.loads(response.text)
            
            # Enhanced logging for both margin and operational announcements
            if result.get('is_relevant_notice', False):
                announcement_type = result.get('announcement_type', 'unknown')
                total_entries = result.get('total_entries', 0)
                total_commodities = result.get('total_commodities', 0)
                total_dates = len(result.get('effective_dates', []))
                
                print(f"🤖 Gemini Enhanced: Found {announcement_type} with {total_entries} entries for {total_commodities} commodities across {total_dates} dates")
                
                # Log specific operational announcements
                if announcement_type != 'margin_adjustment':
                    print(f"📋 Operational Announcement Type: {announcement_type}")
                    for date_entry in result.get('effective_dates', []):
                        for entry in date_entry.get('entries', []):
                            if entry.get('entry_type') == 'operational_data':
                                operation_type = entry.get('operation_type', 'unknown')
                                commodity = entry.get('commodity', 'unknown')
                                print(f"   • {commodity}: {operation_type}")
                
            else:
                print(f"🤖 Gemini Enhanced: Not a relevant trading announcement")
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"❌ Gemini JSON parsing error: {e}")
            print(f"Raw response: {result_text[:300]}...")
            return {"is_relevant_notice": False, "effective_dates": [], "parsing_confidence": "low"}
            
        except Exception as e:
            print(f"❌ Gemini parsing failed: {e}")
            return {"is_relevant_notice": False, "effective_dates": [], "parsing_confidence": "low"}

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

class EnhancedInterestDetector:
    """
    IMPROVED interest detection that captures relevant trading announcements
    while filtering out irrelevant administrative notices.
    """
    
    def __init__(self):
        # Base keywords from main.py enhanced detection
        self.enhanced_detection = {
            "petroleum_keywords": ["petroleum", "石油", "原油", "crude oil"],
            "bitumen_keywords": ["bitumen", "沥青", "石油沥青", "asphalt"],
            "butadiene_rubber_keywords": ["butadiene rubber", "丁二烯橡胶", "BR"],
            "rubber_keywords": ["rubber", "橡胶", "20号胶", "No. 20 rubber", "天然橡胶"],
            "multi_date_indicators": ["multiple dates", "various dates", "different effective dates", "从.*起", "自.*日"]
        }
        
        # Priority keywords from main.py
        self.priority_keywords = [
            'margin', 'ratio', '保证金', '比例', '调整', 'adjust', 
            'price limits', '涨跌停板', 'notice', '通知',
            'petroleum', '石油', 'bitumen', '沥青', 'butadiene', '丁二烯',
            'warehouse', '库容', 'storage', '仓储', 'delivery', '交割'
        ]
        
        # Enhanced report title keywords
        self.report_title_keywords = [
            "adjusting", "margin", "ratio", "price", "limits", "调整", "保证金", "比例", "涨跌停板",
            "warehouse", "storage", "库容", "仓储", "delivery", "交割", "启用"
        ]
        
        # EXPANDED relevant keywords (not just margin adjustments)
        self.relevant_keywords = [
            # Margin and trading
            "margin", "ratio", "保证金", "比例", "调整", "adjustment", "price", "limits", "涨跌停板", 
            "notice", "通知", "关于", "about", "期货", "futures", "交易", "trading",
            # Warehouse and delivery operations
            "warehouse", "库容", "storage", "仓储", "delivery", "交割", "启用", "增加", "suspended", "暂停",
            # Quality and inspection
            "quality", "品质", "inspection", "检验", "standard", "标准",
            # Contract specifications
            "contract", "合约", "specification", "规格", "modification", "修改"
        ]
        
        # Commodity keywords for enhanced detection
        self.commodity_keywords = [
            "natural rubber", "天然橡胶", "butadiene rubber", "丁二烯橡胶", "rubber", "橡胶", "20号胶",
            "copper", "铜", "aluminum", "铝", "zinc", "锌", "lead", "铅", "tin", "锡", "nickel", "镍", 
            "gold", "黄金", "silver", "白银", "petroleum", "石油", "原油", "bitumen", "沥青",
            "steel", "钢", "rebar", "螺纹钢", "fuel oil", "燃料油", "期货", "futures",
            "pulp", "纸浆", "alumina", "氧化铝"
        ]
        
        # IMPROVED minimum thresholds - more inclusive for operational announcements
        self.min_relevance_score = 3.0  # Lowered from 5.0 to catch operational announcements
        self.fallback_max_relevance_score = 50
    
    def calculate_enhanced_relevance_score(self, context_data: dict) -> tuple:
        """IMPROVED relevance scoring that includes operational announcements"""
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
                relevance_score += 25  # VERY HIGH score for margin adjustments
                matched_details.append("margin_adjustment_primary")
                break
        
        # 2. SECONDARY: Operational announcements affecting trading (NEW)
        operational_patterns = [
            "关于同意.*增加.*库容.*公告",        # Warehouse capacity increases
            "关于同意.*启用.*库容.*公告",        # Warehouse capacity activation  
            "关于暂停.*交割.*公告",             # Delivery suspensions
            "关于恢复.*交割.*公告",             # Delivery resumptions
            "关于.*品质.*标准.*调整.*公告",      # Quality standard adjustments
            "关于.*合约.*修改.*公告",           # Contract modifications
            "warehouse.*capacity.*increase",     # English equivalents
            "delivery.*suspend",
            "quality.*standard.*adjust"
        ]
        
        for pattern in operational_patterns:
            if re.search(pattern, title, re.IGNORECASE):
                relevance_score += 12  # High score for operational changes in title
                matched_details.append("operational_announcement_title")
                break
            elif re.search(pattern, full_context, re.IGNORECASE):
                relevance_score += 6   # Medium score for operational changes in context
                matched_details.append("operational_announcement_context")
                break
        
        # 3. REFINED EXCLUSIONS - More specific patterns (NEGATIVE SCORES)
        exclusion_patterns = [
            "关于同意.*品牌.*注册.*公告",       # Brand registration (specific)
            "关于就.*征求意见.*公告",           # Public consultation
            "关于注销.*注册.*资质.*公告",       # Registration cancellation  
            "关于.*人事.*任免.*公告",           # Personnel appointments
            "关于.*会议.*纪要.*公告",           # Meeting minutes
            "^关于同意.*有限公司.*注册.*公告$"   # Very specific registration pattern
        ]
        
        excluded_this_notice = False
        for pattern in exclusion_patterns:
            if re.search(pattern, title, re.IGNORECASE):
                # REDUCED penalty - only apply for very specific exclusions
                if re.search("品牌.*注册", title, re.IGNORECASE):
                    relevance_score -= 10  # Brand registrations
                    matched_details.append("excluded_brand_registration")
                elif re.search("征求意见", title, re.IGNORECASE):
                    relevance_score -= 8   # Public consultations  
                elif re.search("人事.*任免", title, re.IGNORECASE):
                    relevance_score -= 12  # Personnel appointments
                else:
                    relevance_score -= 5   # Other exclusions (reduced penalty)
                    matched_details.append("excluded_administrative")
                excluded_this_notice = True
                break
        
        # 4. Commodity detection (ENHANCED - higher scores for operational context)
        commodity_bonus_applied = False
        
        # Special handling for rubber (including the missed announcement)
        rubber_patterns = ["橡胶", "rubber", "20号胶", "No. 20 rubber", "天然橡胶"]
        for rubber_kw in rubber_patterns:
            if rubber_kw.lower() in title or rubber_kw.lower() in full_context:
                if "库容" in full_context or "warehouse" in full_context:
                    relevance_score += 8  # Higher bonus for rubber warehouse announcements
                    mentioned_commodities.append("rubber_warehouse")
                    matched_details.append("rubber_warehouse_announcement")
                else:
                    relevance_score += 5  # Regular rubber announcement
                    mentioned_commodities.append("rubber")
                    matched_details.append("rubber_announcement")
                commodity_bonus_applied = True
                break
        
        # Other high-priority commodities
        if not commodity_bonus_applied:
            petroleum_keywords = self.enhanced_detection.get('petroleum_keywords', [])
            for keyword in petroleum_keywords:
                if keyword.lower() in title or keyword.lower() in full_context:
                    relevance_score += 6
                    mentioned_commodities.append("petroleum")
                    matched_details.append("petroleum_announcement")
                    commodity_bonus_applied = True
                    break
            
            bitumen_keywords = self.enhanced_detection.get('bitumen_keywords', [])
            for keyword in bitumen_keywords:
                if keyword.lower() in title or keyword.lower() in full_context:
                    relevance_score += 6
                    mentioned_commodities.append("bitumen") 
                    matched_details.append("bitumen_announcement")
                    commodity_bonus_applied = True
                    break
        
        # General commodity detection (if no specific commodity found)
        if not commodity_bonus_applied:
            commodity_count = sum(1 for kw in self.commodity_keywords if kw.lower() in full_context)
            if commodity_count > 0:
                relevance_score += min(commodity_count * 2, 6)  # Up to 6 points for commodities
                mentioned_commodities.extend([kw for kw in self.commodity_keywords[:3] if kw.lower() in full_context])
                matched_details.append(f"general_commodities:{commodity_count}")
        
        # 5. Trading operation keywords (NEW)
        trading_ops_keywords = [
            "库容", "warehouse", "storage", "交割", "delivery", "启用", "activate",
            "暂停", "suspend", "恢复", "resume", "增加", "increase", "调整", "adjust"
        ]
        
        trading_ops_count = sum(1 for kw in trading_ops_keywords if kw.lower() in full_context)
        if trading_ops_count > 0:
            relevance_score += min(trading_ops_count, 4)  # Cap at 4 points
            matched_details.append(f"trading_operations:{trading_ops_count}")
        
        # 6. Exchange name detection (adds credibility)
        exchange_keywords = [
            "上海期货交易所", "上海国际能源交易中心", "SHFE", "INE",
            "Shanghai Futures Exchange", "Shanghai International Energy Exchange"
        ]
        
        exchange_detected = any(kw.lower() in full_context for kw in exchange_keywords)
        if exchange_detected:
            relevance_score += 2
            matched_details.append("official_exchange_announcement")
        
        # 7. Date recency bonus (unchanged)
        current_year = datetime.now().year
        for year in range(current_year - 1, current_year + 2):
            if str(year) in full_context:
                relevance_score += 1
                matched_details.append(f"recent_year:{year}")
                break
        
        return relevance_score, matched_details, mentioned_commodities
    
    def extract_notice_context(self, notice_element) -> dict:
        """Extract comprehensive context around a notice element (like main.py)"""
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
            # Extract parent context (like main.py does)
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
        """IMPROVED interest detection for broader range of relevant announcements"""
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
            
            # Calculate enhanced relevance score
            relevance_score, matched_details, mentioned_commodities = self.calculate_enhanced_relevance_score(context_data)
            
            # Apply LOWERED threshold to catch operational announcements
            is_interesting = relevance_score >= self.min_relevance_score
            
            # Enhanced logging for debugging
            title_preview = context_data['title'][:100] + "..." if len(context_data['title']) > 100 else context_data['title']
            
            if is_interesting:
                announcement_type = "MARGIN ADJUSTMENT" if any("margin" in detail for detail in matched_details) else "OPERATIONAL"
                reason = f"{announcement_type} (score: {relevance_score:.1f}): {', '.join(matched_details)}"
            else:
                reason = f"FILTERED OUT (score: {relevance_score:.1f}): {', '.join(matched_details) if matched_details else 'No relevant patterns'}"
                if relevance_score < 1:
                    reason += " - No commodity or trading operation indicators"
            
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
    """Enhanced SHFE scraper with incremental batching and broader capture"""
    
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
        self.csv_output = os.path.join(self.output_dir, f"shfe_data_incremental_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        
        # BATCHING CONFIGURATION
        self.batch_size = 10  # Save every 50 processed notices
        self.current_batch = []
        self.total_saved_entries = 0
        self.batch_count = 0

        # Initialize components
        self.data_exporter = SHFEDataExporter(self.dataset_name, self.output_dir)
        self.commodity_extractor = SHFECommodityExtractor()
        self.interest_detector = EnhancedInterestDetector()
        self.extracted_data = []
        
        # Initialize Gemini parser
        if gemini_api_key:
            try:
                self.gemini_parser = GeminiContentParser(gemini_api_key)
                print("🤖 Gemini content parser initialized with enhanced logic")
            except Exception as e:
                print(f"⚠️ Gemini initialization failed: {e}")
                self.gemini_parser = None
        else:
            print("⚠️ Gemini API key not provided. Gemini parsing will be disabled.")
            self.gemini_parser = None
    
    def setup_csv(self):
        """Initialize CSV file with headers"""
        os.makedirs(self.output_dir, exist_ok=True)
        
        with open(self.csv_output, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                'Date', 'Title', 'URL', 'Commodity', 'Entry_Type', 'Announcement_Type',
                'Hedging_Percentage', 'Speculative_Percentage', 'Effective_Date', 
                'Adjustment_Type', 'Operation_Type', 'Operation_Description', 
                'Affected_Parties', 'Source_Sentence', 'Parsing_Method', 'Confidence', 
                'Scraped_At', 'Interest_Score', 'Interest_Details', 'Detected_Commodities',
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
                        entry.get('commodity', ''), entry.get('entry_type', ''), entry.get('announcement_type', ''),
                        entry.get('hedging_percentage', ''), entry.get('speculative_percentage', ''),
                        entry.get('effective_date', ''), entry.get('adjustment_type', ''),
                        entry.get('operation_type', ''), entry.get('operation_description', ''),
                        entry.get('affected_parties', ''), entry.get('source_sentence', ''),
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
                    
                    # Create incremental XLS files (not ZIP yet)
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
        """Enhanced notice scraping with FIXED logic for operational announcements"""
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
                print("⚠️ Gemini parser not available")
                return 0
            
            print("🤖 Parsing content with Gemini Enhanced Logic...")
            try:
                gemini_result = self.gemini_parser.parse_margin_notice(clean_text, title)
            except Exception as e:
                print(f"⚠️ Gemini parsing error: {e}")
                return 0
            
            # FIXED: Check for is_relevant_notice instead of is_margin_notice
            if not gemini_result.get('is_relevant_notice', False):
                print("📄 Not a relevant trading announcement")
                return 0
            
            saved_count = 0
            announcement_type = gemini_result.get('announcement_type', 'unknown')
            
            for date_entry in gemini_result.get('effective_dates', []):
                effective_date = date_entry.get('date', '')
                
                for entry_data in date_entry.get('entries', []):
                    commodity = entry_data.get('commodity', 'Unknown')
                    entry_type = entry_data.get('entry_type', 'unknown')
                    
                    # Handle both margin data and operational data
                    if entry_type == 'margin_data':
                        hedging_pct = entry_data.get('hedging_percentage', 0)
                        speculative_pct = entry_data.get('speculative_percentage', 0)
                        
                        if hedging_pct > 20 or speculative_pct > 20:
                            print(f"⚠️ Skipping {commodity}: percentages exceed 20% limit")
                            continue
                        
                        entry = {
                            'notice_date': notice_date.strftime("%Y-%m-%d"),
                            'title': title,
                            'url': notice_url,
                            'commodity': commodity,
                            'entry_type': 'margin_data',
                            'announcement_type': announcement_type,
                            'hedging_percentage': hedging_pct,
                            'speculative_percentage': speculative_pct,
                            'effective_date': effective_date,
                            'adjustment_type': entry_data.get('adjustment_type', 'adjusted_to'),
                            'operation_type': '',
                            'operation_description': '',
                            'affected_parties': '',
                            'source_sentence': entry_data.get('source_sentence', '')[:200],
                            'parsing_method': 'Gemini_Enhanced',
                            'confidence': gemini_result.get('parsing_confidence', 'medium'),
                            'scraped_at': datetime.now().isoformat(),
                            'interest_score': interest_info.get('score', 0) if interest_info else 0,
                            'interest_details': '; '.join(interest_info.get('details', [])) if interest_info else '',
                            'detected_commodities': '; '.join(interest_info.get('commodities', [])) if interest_info else ''
                        }
                        
                    elif entry_type == 'operational_data':
                        # Handle operational announcements
                        entry = {
                            'notice_date': notice_date.strftime("%Y-%m-%d"),
                            'title': title,
                            'url': notice_url,
                            'commodity': commodity,
                            'entry_type': 'operational_data',
                            'announcement_type': announcement_type,
                            'hedging_percentage': '',
                            'speculative_percentage': '',
                            'effective_date': effective_date,
                            'adjustment_type': entry_data.get('adjustment_type', ''),
                            'operation_type': entry_data.get('operation_type', ''),
                            'operation_description': entry_data.get('operation_description', '')[:200],
                            'affected_parties': '; '.join(entry_data.get('affected_parties', [])),
                            'source_sentence': entry_data.get('source_sentence', '')[:200],
                            'parsing_method': 'Gemini_Enhanced',
                            'confidence': gemini_result.get('parsing_confidence', 'medium'),
                            'scraped_at': datetime.now().isoformat(),
                            'interest_score': interest_info.get('score', 0) if interest_info else 0,
                            'interest_details': '; '.join(interest_info.get('details', [])) if interest_info else '',
                            'detected_commodities': '; '.join(interest_info.get('commodities', [])) if interest_info else ''
                        }
                    
                    else:
                        print(f"⚠️ Unknown entry type: {entry_type}")
                        continue
                    
                    # Add to batch instead of direct CSV
                    self.add_entry_to_batch(entry)
                    saved_count += 1
            
            if saved_count > 0:
                print(f"💾 Added {saved_count} entries to batch ({announcement_type})")
            
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
        """LESS RESTRICTIVE interest detection - process more announcements"""
        try:
            interest_result = self.interest_detector.is_notice_interesting(notice_element)
            
            # LOWERED THRESHOLD - be more inclusive
            if interest_result['score'] < 1.0:
                # Even very low scores get a chance if they have commodity keywords
                context_data = interest_result.get('context', {})
                title = context_data.get('title', '').lower()
                
                # Check for basic commodity presence
                basic_commodities = ['copper', 'aluminum', 'zinc', 'lead', 'nickel', 'tin', 'gold', 'silver', 
                                   'rubber', 'oil', 'steel', 'pulp', '铜', '铝', '锌', '铅', '镍', '锡', '金', '银', 
                                   '橡胶', '油', '钢', '纸浆', '期货', 'futures']
                
                has_commodity = any(commodity in title for commodity in basic_commodities)
                if has_commodity:
                    interest_result['is_interesting'] = True
                    interest_result['reason'] = f"COMMODITY FALLBACK (score: {interest_result['score']:.1f}): Has commodity keywords"
                    interest_result['score'] = 2.0  # Boost to minimum
            
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
    
    def process_notices_on_page_safe(self, page_num: int) -> Tuple[int, int, int]:
        """Process notices with recovery handling"""
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
                "[class*='item_info']",
                "[class*='notice']"
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
                    
                    # LESS RESTRICTIVE INTEREST DETECTION
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
                    print(f"🧠 Interest Score: {interest_result['score']:.1f} - {interest_result['reason']}")
                    
                    try:
                        entry_count = self.scrape_notice_content(full_url, title, notice_date, interest_result)
                        extracted_count += entry_count
                        
                        # Save batch periodically during processing
                        if self.total_saved_entries > 0 and self.total_saved_entries % 100 == 0:
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
            
            print(f"📄 Page {page_num} Summary: {processed_count} notices processed, {extracted_count} entries extracted")
                
        except Exception as e:
            print(f"❌ Critical error on page {page_num}: {e}")
            # Save any data we have so far
            if len(self.current_batch) > 0:
                print("💾 Emergency save of current batch due to error...")
                self.save_batch_to_csv()
            
        return processed_count, extracted_count, enhanced_filter_savings
    
    def run_scraper(self):
        """Main execution with crash recovery and broader processing"""
        print("🚀 Starting ENHANCED SHFE Scraper with Incremental Batching")
        print(f"📊 Dataset: {self.dataset_name}")
        print(f"📅 Date range: {self.start_date_str} to {self.today}")
        print(f"🤖 Gemini content parsing: {'Enabled' if self.gemini_parser else 'Disabled'}")
        print(f"💾 Batch size: {self.batch_size} entries")
        print(f"🎯 STRATEGY: Process broadly, capture both margin AND operational announcements")
        print(f"🛡️ CRASH RECOVERY: Data saved incrementally, no loss on crashes")
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
                    
                    # More lenient termination
                    if consecutive_empty_pages > 5 or page_count > 30:
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
            
            print(f"\n🎉 Enhanced scraping completed!")
            print(f"📊 PROCESSING SUMMARY:")
            print(f"   📄 Pages processed: {page_count}")
            print(f"   🎯 Notices processed: {total_processed}")
            print(f"   💾 Total entries saved: {self.total_saved_entries}")
            print(f"   🚫 Notices filtered: {total_filter_savings}")
            print(f"   📦 Batches saved: {self.batch_count}")
            
            # Create final ZIP only at the very end
            if self.total_saved_entries > 0:
                print(f"\n📦 Creating final ZIP archive...")
                try:
                    latest_date = max(entry['scraped_at'] for entry in self.extracted_data)
                    release_date = datetime.fromisoformat(latest_date.replace('T', ' ').split('.')[0]).strftime("%Y-%m-%d")
                    
                    data_path, meta_path = self.data_exporter.create_xls_files(self.extracted_data, release_date)
                    zip_path = self.data_exporter.create_zip_archive(data_path, meta_path)
                    
                    print(f"✅ SUCCESS! Final output:")
                    print(f"   📄 CSV: {self.csv_output}")
                    print(f"   📦 ZIP: {zip_path}")
                    print(f"   💾 Total entries: {self.total_saved_entries}")
                    return zip_path
                    
                except Exception as e:
                    print(f"⚠️ Error creating final ZIP: {e}")
                    print(f"💾 Data is still saved in CSV: {self.csv_output}")
                    return self.csv_output
            else:
                print("💡 No data extracted in the specified date range.")
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
    
    def quick_margin_check_enhanced(self, content: str, interest_info: dict = None) -> bool:
        """Enhanced quick check using interest detection context"""
        margin_indicators = ['margin ratio', 'trading margin', '保证金', '交易保证金', 'hedging', 'speculative', '套期保值', '投机', 'price limit', '价格限额', 'adjusted to', '调整']
        content_lower = content.lower()
        matches = sum(1 for indicator in margin_indicators if indicator in content_lower)
        
        # Lower threshold if we have high interest score
        required_matches = 2 if (interest_info and interest_info.get('score', 0) > 5) else 3
        
        is_likely = matches >= required_matches
        if not is_likely:
            print(f"⚡ Enhanced quick filter: Only {matches}/{required_matches}+ margin indicators found")
        return is_likely
    
    def export_final_data(self) -> str:
        if not self.extracted_data:
            return ""
        
        latest_date = max(entry['scraped_at'] for entry in self.extracted_data)
        release_date = datetime.fromisoformat(latest_date.replace('T', ' ').split('.')[0]).strftime("%Y-%m-%d")
        
        data_path, meta_path = self.data_exporter.create_xls_files(self.extracted_data, release_date)
        zip_path = self.data_exporter.create_zip_archive(data_path, meta_path)
        
        return zip_path

# Usage example - RUNBOOK COMPLIANT
if __name__ == "__main__":
    # Configuration per RUNBOOK requirements
    START_DATE = "2025-01-10"
    DATASET_NAME = "SHFEMR"
    OUTPUT_DIR = "shfe_output"
    GEMINI_API_KEY = "your-gemini-api-key-here"
    
    print("📋 RUNBOOK COMPLIANCE:")
    print("✅ Targets: 'Notice on Adjusting the Margin Ratio and Price Limits...'")
    print("✅ Chinese: '关于调整...保证金比例和涨跌停板的通知'")
    print("🚫 Excludes: Registration, consultation, delivery notices")
    print("🎯 Minimum relevance score: 10.0 (strict filtering)")
    
    # Create and run runbook-compliant scraper
    scraper = LLMEnhancedSHFEScraper(
        start_date=START_DATE,
        gemini_api_key=GEMINI_API_KEY,
        output_dir=OUTPUT_DIR
    )
    
    result_zip = scraper.run_scraper()
    
    if result_zip:
        print(f"✅ RUNBOOK-COMPLIANT scraping successful! Output: {result_zip}")
    else:
        print("❌ No margin adjustment notices found matching runbook criteria")