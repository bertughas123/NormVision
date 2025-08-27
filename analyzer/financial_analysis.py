"""
Financial Analysis Module for Norm Holding
Analyzes customer payment compliance, collection periods, and credit limit compliance
"""

import pandas as pd
import json
import re
from datetime import datetime

class FinancialAnalyzer:
    def __init__(self):
        self.vade_file_path = r'C:\Users\acer\Desktop\NORM HOLDING\datasforfinalblock\Musteri_Ortalama_Vade_Raporu.xlsx'
        self.balance_file_path = r'C:\Users\acer\Desktop\NORM HOLDING\datasforfinalblock\Yuruyen_Bakiyeli_Musteri_Ekstresi.xlsx'
        self.sales_file_path = r'C:\Users\acer\Desktop\NORM HOLDING\datasforfinalblock\LLM_Input_Satis_Analizi.json'
    
    def clean_currency_value(self, value_str):
        """
        Clean currency values by removing TRY suffix and other formatting
        Handles various formats like: "1000 TRY", "1.000,50 TRY", "25.435.852,83 - 02.07.2025", etc.
        """
        if not value_str or pd.isna(value_str):
            return 0.0
            
        # Convert to string and strip whitespace
        clean_str = str(value_str).strip()
        
        # Remove "TRY" suffix (case insensitive)
        clean_str = re.sub(r'\s*TRY\s*$', '', clean_str, flags=re.IGNORECASE)
        
        # For sales data that might contain dates, extract only the number part at the beginning
        # Pattern: "25.435.852,83 - 02.07.2025" -> "25.435.852,83"
        date_pattern = r'\s*-\s*\d{2}\.\d{2}\.\d{4}.*$'
        if re.search(date_pattern, clean_str):
            clean_str = re.sub(date_pattern, '', clean_str)
        
        # Remove any remaining non-numeric characters except digits, commas, periods, and minus signs
        clean_str = re.sub(r'[^\d,.,-]', '', clean_str)
        
        # Handle different decimal separator conventions
        # If there are multiple periods and commas, assume European format (1.000,50)
        if '.' in clean_str and ',' in clean_str:
            # European format: 1.000,50 -> 1000.50
            parts = clean_str.split(',')
            if len(parts) == 2:
                integer_part = parts[0].replace('.', '')  # Remove thousand separators
                decimal_part = parts[1]
                clean_str = f"{integer_part}.{decimal_part}"
        elif ',' in clean_str and clean_str.count(',') == 1:
            # Check if comma is decimal separator or thousand separator
            comma_pos = clean_str.find(',')
            after_comma = clean_str[comma_pos + 1:]
            
            # If 1-2 digits after comma, it's likely decimal separator
            if len(after_comma) <= 2 and after_comma.isdigit():
                clean_str = clean_str.replace(',', '.')
            else:
                # Otherwise, it's thousand separator
                clean_str = clean_str.replace(',', '')
        elif ',' in clean_str:
            # Multiple commas - treat as thousand separators
            clean_str = clean_str.replace(',', '')
        
        # Convert to float
        try:
            return float(clean_str)
        except (ValueError, TypeError):
            print(f"Warning: Could not convert '{value_str}' to numeric value")
            return 0.0
    
    def extract_payment_compliance(self):
        """
        Extract company's compliance with payment terms as a percentage
        """
        try:
            vade_df = pd.read_excel(self.vade_file_path)
            
            if not vade_df.empty:
                company_name = vade_df['Ad'].iloc[0]
                payment_condition = vade_df['ÖdemeKoşul'].iloc[0] if 'ÖdemeKoşul' in vade_df.columns else None
                deviation = vade_df['Sapma'].iloc[0] if 'Sapma' in vade_df.columns else None
                
                # Calculate compliance percentage
                # If customer pays early (negative deviation), compliance can exceed 100%
                if payment_condition and deviation is not None:
                    # Base compliance assuming payment_condition is the agreed term
                    base_compliance = 100
                    # If deviation is negative (early payment), add to compliance
                    # If deviation is positive (late payment), subtract from compliance
                    compliance_percentage = base_compliance - (deviation / payment_condition) * 100
                    compliance_percentage = max(0, compliance_percentage)  # Ensure non-negative
                    
                    if deviation < 0:  # Early payment
                        compliance_percentage = base_compliance + abs(deviation / payment_condition) * 20
                    
                    return {
                        "company_name": company_name,
                        "compliance_percentage": round(compliance_percentage, 2),
                        "payment_condition_days": payment_condition,
                        "actual_payment_deviation": deviation
                    }
            
            return None
        except Exception as e:
            print(f"Error extracting payment compliance: {e}")
            return None
    
    def calculate_average_collection_period(self):
        """
        Calculate average collection period using (Receivables/Sales) x Number of days
        """
        try:
            vade_df = pd.read_excel(self.vade_file_path)
            balance_df = pd.read_excel(self.balance_file_path)
            
            # Get receivables from balance sheet
            receivables = None
            sales_amount = None
            
            # Extract receivables (Cari Riski)
            for i, row in balance_df.iterrows():
                if 'Cari Riski' in str(row['Alan']):
                    receivables = self.clean_currency_value(row['Değer'])
            
            # Extract sales data from vade report
            if not vade_df.empty:
                sales_data = vade_df['Toplam FatFatOrtVade'].iloc[0]
                if sales_data:
                    sales_amount = self.clean_currency_value(sales_data)
            
            if receivables is not None and sales_amount and sales_amount > 0:
                # Calculate collection period (assuming 365 days in a year)
                collection_period = (receivables / sales_amount) * 365
                return {
                    "receivables_amount": receivables,
                    "sales_amount": sales_amount,
                    "average_collection_period_days": round(collection_period, 2)
                }
            
            return None
        except Exception as e:
            print(f"Error calculating collection period: {e}")
            return None
    
    def determine_credit_limit_compliance(self):
        """
        Determine credit limit compliance and payment method
        """
        try:
            balance_df = pd.read_excel(self.balance_file_path)
            # Initialize variables
            credit_limit = None
            current_risk = None
            check_risk = None
            promissory_note_risk = None
            
            # Extract relevant values
            for i, row in balance_df.iterrows():
                alan = str(row['Alan'])
                deger = str(row['Değer'])
                
                if 'Cari Limiti' in alan:
                    credit_limit = self.clean_currency_value(deger)
                
                elif 'Cari Riski' in alan:
                    current_risk = self.clean_currency_value(deger)
                
                elif 'Kendi Çek Riski' in alan:
                    check_risk = self.clean_currency_value(deger)
                
                elif 'Senet Riski' in alan:
                    promissory_note_risk = self.clean_currency_value(deger)
            
            # Determine compliance
            compliance = "NO"
            if credit_limit and current_risk is not None:
                if current_risk <= credit_limit:
                    compliance = "YES"
            
            # Determine payment method and terms
            payment_method = None
            payment_period_days = None
            
            if check_risk and check_risk > 0:
                payment_method = "çek"
                payment_period_days = "30-45"
            elif promissory_note_risk and promissory_note_risk > 0:
                payment_method = "senet"
                payment_period_days = "30-45"
            
            return {
                "credit_limit_compliance": compliance,
                "credit_limit_amount": credit_limit,
                "current_risk_amount": current_risk,
                "payment_method": payment_method,
                "payment_period_days": payment_period_days,
                "check_risk": check_risk,
                "promissory_note_risk": promissory_note_risk
            }
            
        except Exception as e:
            print(f"Error determining credit limit compliance: {e}")
            return None
    
    def load_existing_sales_data(self):
        """
        Load existing sales analysis data
        """
        try:
            with open(self.sales_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading sales data: {e}")
            return {}
    
    def generate_comprehensive_financial_json(self):
        """
        Combine all financial analysis into a comprehensive JSON format
        """
        # Get all analysis results
        payment_compliance = self.extract_payment_compliance()
        collection_period = self.calculate_average_collection_period()
        credit_compliance = self.determine_credit_limit_compliance()
        sales_data = self.load_existing_sales_data()
        
        # Create simplified financial analysis
        financial_analysis = sales_data.copy()  # Start with sales data
        
        # Add payment compliance data
        if payment_compliance:
            financial_analysis["musteri_adi"] = payment_compliance["company_name"]
            financial_analysis["vadeye_uyum"] = payment_compliance["compliance_percentage"]
        
        # Add collection period data
        if collection_period:
            financial_analysis["alacaklar_tutari"] = collection_period["receivables_amount"]
            financial_analysis["satis_tutari"] = collection_period["sales_amount"]
            financial_analysis["ortalama_tahsilat_suresi_gun"] = collection_period["average_collection_period_days"]
        
        # Add credit compliance data
        if credit_compliance:
            financial_analysis["kredi_limit_uyumu"] = credit_compliance["credit_limit_compliance"]
            financial_analysis["kredi_limiti"] = credit_compliance["credit_limit_amount"]
            financial_analysis["mevcut_risk"] = credit_compliance["current_risk_amount"]
            financial_analysis["odeme_yontemi"] = credit_compliance["payment_method"]
            # Only add check_risk if payment method is çek
            if credit_compliance["payment_method"] == "çek":
                financial_analysis["cek_riski"] = credit_compliance["check_risk"]
        
        return financial_analysis
    
def main():
    """
    Main function to run the financial analysis
    """
    analyzer = FinancialAnalyzer()
    
    print("Starting comprehensive financial analysis...")
    
    # Generate comprehensive analysis
    financial_json = analyzer.generate_comprehensive_financial_json()
    
    # Save to file
    output_file = r'C:\Users\acer\Desktop\NORM HOLDING\datasforfinalblock\LLM_Input_Finansal_Analiz.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(financial_json, f, ensure_ascii=False, indent=2)
    
    print(f"Financial analysis completed and saved to: {output_file}")
    
    # Print key findings
    print("\n=== KEY FINANCIAL FINDINGS ===")
    if financial_json.get("vadeye_uyum"):
        print(f"Payment Compliance: {financial_json['vadeye_uyum']}%")
    
    if financial_json.get("ortalama_tahsilat_suresi_gun"):
        print(f"Average Collection Period: {financial_json['ortalama_tahsilat_suresi_gun']} days")
    
    if financial_json.get("kredi_limit_uyumu"):
        print(f"Credit Limit Compliance: {financial_json['kredi_limit_uyumu']}")
    
    return financial_json

if __name__ == "__main__":
    result = main()
