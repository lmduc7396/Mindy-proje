# Database Schema Reference Guide
**Dragon Capital Financial Data Pipeline**

## Overview
This document provides a comprehensive reference for all database tables created and maintained by the financial data pipeline. Tables are organized by functional area with detailed schema information, relationships, and data characteristics.

---

## Table of Contents
1. [Financial Statement Tables](#financial-statement-tables)
2. [Market Data Tables](#market-data-tables)
3. [Banking Analytics Tables](#banking-analytics-tables)
4. [Brokerage Analytics Tables](#brokerage-analytics-tables)
5. [Reference Data Tables](#reference-data-tables)
6. [Economic Data Tables](#economic-data-tables) (includes Monthly_Income, Container_volume)
7. [Table Relationships](#table-relationships)
8. [Data Update Patterns](#data-update-patterns)

---

## Financial Statement Tables

### FA_Quarterly
**Purpose**: Quarterly financial statement data for all listed companies
**Update Frequency**: Weekly
**Data Range**: 2016 - Present
**Row Count**: ~500,000+
ß
| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **TICKER** | NVARCHAR(50) | NO | Stock symbol (3 letters) | 'VNM' |
| **KEYCODE** | NVARCHAR(50) | NO | Financial metric identifier | 'Net_Revenue' |
| **DATE** | NVARCHAR(50) | NO | Quarter in YYYYQX format | '2024Q3' |
| VALUE | FLOAT | YES | Metric value in VND | 15234567890.0 |
| YEAR | BIGINT | YES | Extracted year for filtering | 2024 |
| YoY | FLOAT | YES | Year-over-year growth rate | 0.085 (8.5%) |

**Primary Key**: TICKER + KEYCODE + DATE
**Common KEYCODE Values**:
- Income Statement: Net_Revenue, COGS, Gross_Profit, EBIT, EBITDA, NPAT, NPATMI
- Balance Sheet: Total_Asset, Total_Liabilities, TOTAL_Equity, Cash, ST_Debt, LT_Debt
- Cash Flow: Operating_CF, Inv_CF, Fin_CF, FCF, Capex
- Margins: Gross_Margin, EBIT_Margin, EBITDA_Margin, NPAT_Margin

---

### FA_Annual
**Purpose**: Annual financial statement data
**Update Frequency**: Weekly
**Data Range**: 2016 - Present
**Row Count**: ~125,000+

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **TICKER** | NVARCHAR(50) | NO | Stock symbol | 'VNM' |
| **KEYCODE** | NVARCHAR(50) | NO | Financial metric identifier | 'Net_Revenue' |
| **DATE** | NVARCHAR(50) | NO | Year as string | '2024' |
| VALUE | FLOAT | YES | Annual metric value in VND | 61234567890.0 |
| YEAR | BIGINT | YES | Year as integer | 2024 |
| YoY | FLOAT | YES | Year-over-year growth | 0.092 |

**Primary Key**: TICKER + KEYCODE + DATE
**Note**: Contains same KEYCODE values as FA_Quarterly but with annual aggregations

---

## Market Data Tables

### Market_Data
**Purpose**: Comprehensive daily market data including OHLC prices, valuation multiples, and EV/EBITDA
**Update Frequency**: Daily
**Data Range**: 2018 - Present
**Row Count**: ~1,400,000+

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **TICKER** | VARCHAR(10) | NO | Stock symbol (extracted from PRIMARYSECID) | 'VNM' |
| **TRADE_DATE** | DATE | NO | Trading date | '2024-09-23' |
| PE | FLOAT | YES | Price-to-Earnings ratio | 18.5 |
| PB | FLOAT | YES | Price-to-Book ratio | 3.2 |
| PS | FLOAT | YES | Price-to-Sales ratio | 2.8 |
| PX_OPEN | FLOAT | YES | Opening price | 67500 |
| PX_HIGH | FLOAT | YES | Daily high price | 68200 |
| PX_LOW | FLOAT | YES | Daily low price | 67000 |
| PX_LAST | FLOAT | YES | Closing/Last price | 67800 |
| MKT_CAP | FLOAT | YES | Market capitalization | 145678.5 |
| EV_EBITDA | FLOAT | YES | Enterprise Value/EBITDA ratio | 12.3 |
| UPDATE_TIMESTAMP | DATETIME | YES | Last update timestamp | '2024-09-23 18:30:00' |

**Primary Key**: TICKER + TRADE_DATE
**Data Sources**:
- Bloomberg (SIL.S_BBG_DATA_DWH_ADJUSTED): PE, PB, PS, PX_OPEN, PX_HIGH, PX_LOW, PX_LAST, MKT_CAP
- IRIS (SIL.W_F_IRIS_CALCULATE): EV_EBITDA
**Data Quality Notes**:
- PX_ prefix used for price columns to avoid SQL reserved keywords
- NULL values indicate data not available or not calculable
- Price relationships validated: PX_HIGH >= PX_LAST >= PX_LOW
- Extreme valuation ratios capped (PE < 1000, PB < 100, PS < 100)
- Updated via standalone valuation_ohlc_extractor script

---

### MarketCap
**Purpose**: Latest market capitalization snapshot
**Update Frequency**: Daily
**Data Range**: Current snapshot only
**Row Count**: ~1,700 (all listed stocks)

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **TICKER** | NVARCHAR(50) | NO | Stock symbol | 'VNM' |
| CUR_MKT_CAP | FLOAT | YES | Market cap in billions VND | 145678.5 |
| **TRADE_DATE** | DATETIME | YES | Date of snapshot | '2024-09-23' |

**Primary Key**: TICKER + TRADE_DATE
**Note**: Only contains latest values, historical data in separate archive

---

### MarketIndex
**Purpose**: Stock market index historical data (HOSE)
**Update Frequency**: Daily
**Data Range**: 2016 - Present
**Row Count**: ~2,000+

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **COMGROUPCODE** | NVARCHAR(50) | NO | Index identifier | 'VNINDEX' |
| **TRADINGDATE** | DATETIME | NO | Trading date | '2024-09-23' |
| INDEXVALUE | FLOAT | YES | Closing index value | 1285.67 |
| PRIORINDEXVALUE | FLOAT | YES | Previous day's close | 1278.45 |
| HIGHEST | FLOAT | YES | Intraday high | 1290.12 |
| LOWEST | FLOAT | YES | Intraday low | 1275.30 |
| TOTALSHARE | BIGINT | YES | Total shares traded | 567890123 |
| TOTALVALUE | FLOAT | YES | Total value traded (VND) | 12345678901234 |
| FOREIGNBUYVOLUME | BIGINT | YES | Foreign buying volume | 12345678 |
| FOREIGNSELLVOLUME | BIGINT | YES | Foreign selling volume | 11234567 |

**Primary Key**: COMGROUPCODE + TRADINGDATE

---

## Banking Analytics Tables

### BankingMetrics
**Purpose**: Comprehensive banking metrics including 26 calculated ratios (CA.1-CA.26)
**Update Frequency**: Quarterly with annual aggregates
**Data Range**: 2017 - Present (including forecast years)
**Row Count**: ~10,000+ (actual + forecast)

**Key Columns**:
| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **TICKER** | NVARCHAR(20) | NO | Bank ticker or tier aggregate | 'VCB' or 'SOCB' |
| **YEARREPORT** | INT | NO | Reporting year | 2024 |
| **LENGTHREPORT** | INT | NO | 1-4 for Q1-Q4, 5 for annual | 3 |
| **ACTUAL** | BIT | NO | True=Historical, False=Forecast | 1 |
| DATE | DATE | YES | End date of period | '2024-09-30' |
| DATE_STRING | NVARCHAR(20) | YES | Formatted period | '2024-Q3' or '2024' |
| BANK_TYPE | NVARCHAR(20) | YES | Bank classification | 'SOCB', 'Private_1' |
| PERIOD_TYPE | NVARCHAR(10) | YES | 'Q' for quarterly, 'Y' for annual | 'Q' |

**Financial Metrics** (Human-readable column names):
| Column Name | Description | Typical Range |
|-------------|-------------|---------------|
| TOI | Total Operating Income | 1000-50000 bn VND |
| PBT | Profit Before Tax | 500-30000 bn VND |
| Net Interest Income | Interest revenue net of expense | 500-30000 bn VND |
| OPEX | Operating Expenses | -500 to -20000 bn VND |
| PPOP | Pre-Provision Operating Profit | 500-25000 bn VND |
| Provision expense | Credit provision expense | -100 to -10000 bn VND |
| NPATMI | Net Profit After Tax Minority Interest | 300-20000 bn VND |
| Fees Income | Non-interest fee income | 100-5000 bn VND |
| Net Profit | Net profit after all expenses | 300-20000 bn VND |
| Loan | Total customer loans | 10000-1500000 bn VND |
| Deposit | Total customer deposits | 10000-1500000 bn VND |
| Total Assets | Balance sheet total assets | 50000-2000000 bn VND |
| Total Equity | Total shareholders' equity | 5000-150000 bn VND |
| Provision on Balance Sheet | Accumulated provisions (negative) | -1000 to -50000 bn VND |
| Write-off | Loan write-offs (Nt.220) | 0-5000 bn VND |

**Calculated Banking Ratios** (Human-readable column names):
| Column Name | CA Code | Description | Formula | Typical Range |
|-------------|---------|-------------|---------|---------------|
| LDR | CA.1 | Loan-to-Deposit Ratio | Loan/Deposit | 70-100% |
| CASA | CA.2 | Current/Savings Account ratio | (Nt.121+124+125)/Deposit | 15-40% |
| NPL | CA.3 | Non-Performing Loan ratio | (Nt.68+69+70)/Loan | 0.5-3% |
| ABS NPL | CA.4 | Absolute NPL amount | Nt.68+69+70 | 100-50000 bn VND |
| GROUP 2 | CA.5 | Group 2 loans ratio | Nt.67/Loan | 0.5-2% |
| CIR | CA.6 | Cost-to-Income Ratio | -OPEX/TOI | 30-60% |
| NPL Coverage ratio | CA.7 | Provision coverage of NPL | -Provision/(Nt.68+69+70) | 50-200% |
| Total Credit Balance | CA.8 | Total credit exposure | BS.13+BS.16+Nt.97+Nt.112 | 15000-2000000 bn VND |
| Provision/ Total Loan | CA.9 | Provision to loan ratio | -Provision/Loan | 1-3% |
| Leverage Multiple | CA.10 | Assets to equity ratio | Total Assets/Total Equity | 8-15x |
| Interest Earnings Asset | CA.11 | Interest-earning assets | Sum of earning assets | 40000-1800000 bn VND |
| Interest Bearing Liabilities | CA.12 | Interest-bearing liabilities | Sum of costing liabilities | 35000-1700000 bn VND |
| NIM | CA.13 | Net Interest Margin | NII/Avg(IEA) annualized | 2-5% |
| Customer loans | CA.14 | Total customer lending | BS.13+BS.16 | 10000-1500000 bn VND |
| Loan yield | CA.15 | Average loan interest rate | Interest income/Avg(Loans) | 6-10% |
| ROA | CA.16 | Return on Assets | Net Profit/Avg(Assets) | 0.5-2% |
| ROE | CA.17 | Return on Equity | NPATMI/Avg(Equity) | 10-25% |
| Deposit balance | CA.18 | Interbank deposits | BS.3+BS.5+BS.6 | 1000-100000 bn VND |
| Deposit yield | CA.19 | Average deposit cost | Interest expense/Avg(Deposits) | 3-6% |
| Fees/ Total asset | CA.20 | Fee income efficiency | Fees Income/Avg(Assets) | 0.5-2% |
| Individual % | CA.21 | Retail loans percentage | Nt.89/BS.12 | 20-60% |
| NPL Formation Amount | CA.22 | New NPL in period | (NPL-Write-off)-NPL_prev | -1000 to 5000 bn VND |
| New NPL | CA.23 | NPL formation rate | CA.22/Loan_prev | -1% to 2% |
| Group 2 Formation | CA.24 | New Group 2 loans | (G2+NPL_form)-G2_prev | -500 to 2000 bn VND |
| New G2 | CA.25 | Group 2 formation rate | CA.24/Loan_prev | -0.5% to 1% |
| Overdue_loan | CA.26 | Total overdue loans ratio | NPL + GROUP 2 | 1-5% |

**Primary Key**: TICKER + YEARREPORT + LENGTHREPORT + ACTUAL

**Special TICKER Values for Aggregates**:
- 'SOCB': State-owned commercial banks aggregate
- 'Private_1': Tier 1 private banks
- 'Private_2': Tier 2 private banks
- 'Private_3': Tier 3 private banks
- 'Sector': Entire banking sector

---

### Banking_Drivers
**Purpose**: Earnings quality decomposition analysis - breaks down PBT growth into operational components
**Update Frequency**: Quarterly and Annual (auto-calculated from BankingMetrics)
**Data Range**: 2017 - Present (requires 4+ quarters for meaningful analysis)
**Row Count**: ~8,500+ (quarterly + annual, all comparison types)
**Total Columns**: 104

**Primary Key**: TICKER + PERIOD_TYPE + DATE

---

#### 1. Key Identification Columns (4)

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **TICKER** | NVARCHAR(20) | NO | Bank ticker or tier aggregate | 'VCB' or 'SOCB' |
| **PERIOD_TYPE** | CHAR(1) | NO | 'Q' for quarterly, 'Y' for annual | 'Q' |
| **DATE** | NVARCHAR(20) | NO | Period identifier | '2024-Q1' or '2024' |
| Type | NVARCHAR(50) | YES | Bank classification | 'SOCB', 'Private_1' |

---

#### 2. Source Metrics - Current Period (11)

Base financial metrics for the current reporting period (from BankingMetrics):

| Column | Description | Typical Range |
|--------|-------------|---------------|
| TOI | Total Operating Income | 1000-50000 bn VND |
| Net Interest Income | Interest revenue net of expense | 500-30000 bn VND |
| Fees Income | Non-interest fee income | 100-5000 bn VND |
| OPEX | Operating Expenses | -500 to -20000 bn VND |
| Provision expense | Credit provision expense | -100 to -10000 bn VND |
| PBT | Profit Before Tax | 500-30000 bn VND |
| Loan | Total customer loans | 10000-1500000 bn VND |
| NIM | Net Interest Margin | 2-5% |
| Core TOI | Net Interest Income + Fees Income | 800-40000 bn VND |
| Core PBT | Core TOI + OPEX + Provision | 400-25000 bn VND |
| Non-recurring income | PBT - Core PBT | -5000 to +10000 bn VND |

---

#### 3. Source Metrics - T12M (Trailing 12 Months) (9)

Same metrics averaged/summed over trailing 12 months:

```
Core TOI_T12M
PBT_T12M
OPEX_T12M
Provision expense_T12M
Non-recurring income_T12M
Net Interest Income_T12M
Fees Income_T12M
Loan_T12M
NIM_T12M
```

---

#### 4. Change Calculations (7)

Absolute changes used in driver calculations:

```
Core_TOI_Change       - Change in Core TOI vs comparison period
PBT_Change            - Change in PBT vs comparison period
OPEX_Change           - Change in OPEX vs comparison period
Provision_Change      - Change in Provision vs comparison period
Non_Recurring_Change  - Change in Non-recurring income vs comparison period
NII_Change            - Change in Net Interest Income vs comparison period
Fee_Change            - Change in Fees Income vs comparison period
```

---

#### 5. Source Metrics - QoQ (Quarter-over-Quarter) (9)

Metrics for previous quarter comparison:

```
Core TOI_QoQ
PBT_QoQ
OPEX_QoQ
Provision expense_QoQ
Non-recurring income_QoQ
Net Interest Income_QoQ
Fees Income_QoQ
Loan_QoQ
NIM_QoQ
```

---

#### 6. Source Metrics - YoY (Year-over-Year) (9)

Metrics for same quarter last year comparison:

```
Core TOI_YoY
PBT_YoY
OPEX_YoY
Provision expense_YoY
Non-recurring income_YoY
Net Interest Income_YoY
Fees Income_YoY
Loan_YoY
NIM_YoY
```

---

#### 7. Source Metrics - Prior Year (9)

Metrics from prior year (for annual comparisons):

```
Core TOI_Prior_Year
PBT_Prior_Year
OPEX_Prior_Year
Provision expense_Prior_Year
Non-recurring income_Prior_Year
Net Interest Income_Prior_Year
Fees Income_Prior_Year
Loan_Prior_Year
NIM_Prior_Year
```

---

#### 8. Growth Percentages (5)

| Column | Description | Example |
|--------|-------------|---------|
| Loan_Growth_% | Loan growth percentage | 15.2% |
| PBT_Growth_% | Percentage change in PBT (unsuffixed) | 20.5% |
| PBT_Growth_%_T12M | PBT growth vs T12M average | 18.3% |
| PBT_Growth_%_QoQ | PBT growth vs previous quarter | 5.2% |
| PBT_Growth_%_YoY | PBT growth vs same quarter last year | 22.1% |

---

#### 9. Main Impact Scores - Unsuffixed (10)

Primary earnings driver impacts (comparison basis unclear - see note below):

| Column | Description | Interpretation |
|--------|-------------|----------------|
| Top_Line_Impact | Revenue contribution to PBT growth | Positive = revenue drove growth |
| Cost_Cutting_Impact | Cost management contribution | Positive = expense control helped |
| Non_Recurring_Impact | One-time items contribution | Positive = one-time gains |
| Total_Impact | Sum of above three | Should ≈ ±100% or growth % |
| NII_Impact | Net Interest Income impact | Sub-component of Top_Line |
| Fee_Impact | Fee income impact | Sub-component of Top_Line |
| OPEX_Impact | Operating expense impact | Sub-component of Cost_Cutting |
| Provision_Impact | Provision expense impact | Sub-component of Cost_Cutting |
| Loan_Impact | Loan volume growth impact | Sub-component of NII |
| NIM_Impact | Net Interest Margin impact | Sub-component of NII |

**Note**: Relationship between unsuffixed and _T12M variants needs clarification.

---

#### 10. Main Impact Scores - T12M (Trailing 12 Months) (10)

Earnings driver impacts based on T12M comparison:

```
Top_Line_Impact_T12M
Cost_Cutting_Impact_T12M
Non_Recurring_Impact_T12M
NII_Impact_T12M
Fee_Impact_T12M
OPEX_Impact_T12M
Provision_Impact_T12M
Loan_Impact_T12M
NIM_Impact_T12M
Total_Impact_T12M
```

---

#### 11. Main Impact Scores - QoQ (Quarter-over-Quarter) (10)

Earnings driver impacts based on QoQ comparison:

```
Top_Line_Impact_QoQ
Cost_Cutting_Impact_QoQ
Non_Recurring_Impact_QoQ
NII_Impact_QoQ
Fee_Impact_QoQ
OPEX_Impact_QoQ
Provision_Impact_QoQ
Loan_Impact_QoQ
NIM_Impact_QoQ
Total_Impact_QoQ
```

---

#### 12. Main Impact Scores - YoY (Year-over-Year) (10)

Earnings driver impacts based on YoY comparison:

```
Top_Line_Impact_YoY
Cost_Cutting_Impact_YoY
Non_Recurring_Impact_YoY
NII_Impact_YoY
Fee_Impact_YoY
OPEX_Impact_YoY
Provision_Impact_YoY
Loan_Impact_YoY
NIM_Impact_YoY
Total_Impact_YoY
```

---

#### 13. Control Flags (3)

| Column | Description | Values |
|--------|-------------|--------|
| Small_PBT_Flag | Flag for small PBT adjustment applied | 0 or 1 |
| Impacts_Capped | Flag if impact scores were capped | 0 or 1 |
| Scores_Capped | Flag if raw scores were capped | 0 or 1 |

---

### Column Summary by Category

| Category | Column Count | Description |
|----------|--------------|-------------|
| Identification | 4 | TICKER, Type, DATE, PERIOD_TYPE |
| Current Metrics | 11 | TOI, PBT, NII, Fees, OPEX, Provision, Loan, NIM, Core metrics |
| T12M Metrics | 9 | Trailing 12-month averages |
| Change Calculations | 7 | Absolute changes vs comparison periods |
| QoQ Metrics | 9 | Previous quarter comparisons |
| YoY Metrics | 9 | Same quarter last year comparisons |
| Prior Year Metrics | 9 | Prior year values for annual comparisons |
| Growth Percentages | 5 | PBT and Loan growth rates |
| Impact Scores (Unsuffixed) | 10 | Primary driver impacts |
| Impact Scores (T12M) | 10 | T12M driver impacts |
| Impact Scores (QoQ) | 10 | QoQ driver impacts |
| Impact Scores (YoY) | 10 | YoY driver impacts |
| Control Flags | 3 | Small_PBT, Impacts_Capped, Scores_Capped |
| **TOTAL** | **106** | **Complete schema** |

---

### Comparison Type Explanation

**Three Comparison Perspectives** (for quarterly data only):

1. **T12M (Trailing 12 Months)**:
   - Compares current vs average of last 12 months
   - Smooths seasonality
   - Most stable for trend analysis

2. **QoQ (Quarter-over-Quarter)**:
   - Compares current vs immediately previous quarter
   - Shows short-term momentum
   - Most volatile, sensitive to seasonal effects

3. **YoY (Year-over-Year)**:
   - Compares current vs same quarter last year
   - Eliminates seasonality
   - Standard for quarterly analysis

**Annual Data**: Only has unsuffixed columns (always YoY comparison)

**Impact Score Interpretation**:
All impact scores sum to approximately the PBT growth percentage for their respective comparison type.

Example for Q1 2024:
- PBT_Growth_%_YoY = +20%
- Top_Line_Impact_YoY = +16%
- Cost_Cutting_Impact_YoY = +6%
- Non_Recurring_Impact_YoY = -2%
- Total = 20% ✓

**Calculation Logic**:
1. Calculate Core Earnings:
   - Core TOI = Net Interest Income + Fees Income
   - Core PBT = Core TOI + OPEX + Provision
   - Non-recurring = PBT - Core PBT

2. Compare vs Prior Period (T12M/QoQ/YoY):
   - PBT_Change = Current - Prior
   - Growth_% = (Change / |Prior|) × 100

3. Normalize to Scores (±100%):
   - Top_Line_Score = (Core TOI Change / |PBT Change|) × 100
   - Cost_Score = ((OPEX + Prov Change) / |PBT Change|) × 100
   - Non_Rec_Score = (Non-Rec Change / |PBT Change|) × 100

4. Convert to Impacts (actual %):
   - Top_Line_Impact = (Top_Line_Score × |Growth_%|) / 100

**Special Cases**:
- **Small PBT Adjustment**: If |PBT_Change| < 50B VND, set to 50B to avoid extreme scores (marked with Small_PBT_Flag=1)
- **Score Capping**: Scores capped at ±500% to prevent outliers (marked with Impacts_Capped=1)
- **Loan Impact Approximation**: Loan_Impact = Loan_Growth_% / 2, NIM_Impact = NII_Impact - Loan_Impact

**Example Interpretation**:
> VCB Q1 2024: PBT grew 20% YoY
> - Top_Line_Impact = +16% → Revenue growth contributed 16 percentage points
> - Cost_Cutting_Impact = +6% → Cost management contributed 6 points
> - Non_Recurring_Impact = -2% → One-time charges reduced by 2 points
> - Total = 20% (matches PBT growth)

**Data Quality Notes**:
- First 4 quarters per bank will have NULL impacts (insufficient history for T12M/YoY)
- QoQ only needs 1 prior quarter
- Annual data only has unsuffixed columns (YoY comparison)
- Tier aggregates ('SOCB', 'Sector') calculated same way as individual banks

---

### Bank_Writeoff
**Purpose**: Quarterly writeoff data (Nt.220) for banking sector
**Update Frequency**: Quarterly (user-maintained)
**Data Range**: 2020 - Present
**Row Count**: ~650+ (27 banks × 24 quarters)

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **TICKER** | NVARCHAR(20) | NO | Bank ticker | 'VCB' |
| **DATE** | NVARCHAR(20) | NO | Quarter in Q[1-4]YYYY format | 'Q12025' |
| Writeoff | FLOAT | YES | Writeoff amount (typically negative) | -150000000 |

**Primary Key**: TICKER + DATE

**DATE Format**: `Q[1-4]YYYY` (e.g., Q12025, Q22025, Q32025, Q42025)

**Update Method**:
- Excel upload via `scripts/upload_writeoff_from_excel.py`
- Direct SQL MERGE for quick updates
- Required for banking pipeline to calculate CA.22-CA.25 metrics

---

### Banking_Comments
**Purpose**: Qualitative commentary and analysis notes for banks
**Update Frequency**: Quarterly (automated via AI)
**Data Range**: 2023-Q1 onwards
**Row Count**: Variable

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **TICKER** | NVARCHAR(50) | NO | Bank ticker or 'Sector' for sector-level reports | 'VCB', 'Sector' |
| SECTOR | NVARCHAR(50) | YES | Banking sector/type | 'SOCB', 'Banking' |
| **DATE** | NVARCHAR(50) | NO | Quarter in YYYY-Q# format | '2024-Q3' |
| COMMENT | NVARCHAR(MAX) | YES | AI-generated analysis text | 'Strong credit growth...' |

**Primary Key**: TICKER + DATE

**Special Records**:
- Individual bank comments: `TICKER = <bank_ticker>`, `SECTOR = <bank_type>`
- Sector-level report: `TICKER = 'Sector'`, `SECTOR = 'Banking'`
  - Aggregated quarterly analysis across all banks
  - Auto-generated from individual bank comments

---

## Brokerage Analytics Tables

### BrokerageMetrics
**Purpose**: Long format brokerage financial data with KEYCODE mappings for securities firms
**Update Frequency**: Quarterly with annual aggregates
**Data Range**: 2017 - Present (including forecast years)
**Row Count**: ~292,800+ actual + forecast (30 brokers × 8 years × 5 periods × ~250 KEYCODEs)

**Key Columns**:
| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **TICKER** | NVARCHAR(20) | NO | Broker ticker or 'Sector' | 'SSI' or 'Sector' |
| ORGANCODE | NVARCHAR(50) | YES | Organization code | 'SSI' |
| **YEARREPORT** | INT | NO | Reporting year | 2024 |
| **LENGTHREPORT** | INT | NO | 1-4 for Q1-Q4, 5 for annual | 3 |
| **ACTUAL** | BIT | NO | True=Historical, False=Forecast | 1 |
| QUARTER_LABEL | NVARCHAR(10) | YES | Formatted period label | '1Q24' or '2024' |
| STARTDATE | DATE | YES | Period start date | '2024-07-01' |
| ENDDATE | DATE | YES | Period end date | '2024-09-30' |
| **KEYCODE** | NVARCHAR(100) | NO | Metric identifier (BS.*, IS.*, Notes, Calculated) | 'BS.1' or '7.1.1.4. Bonds' |
| KEYCODE_NAME | NVARCHAR(200) | YES | Human-readable description | 'CURRENT ASSETS' |
| VALUE | FLOAT | YES | Metric value in VND | 5000000000.0 |

**Primary Key**: TICKER + YEARREPORT + LENGTHREPORT + ACTUAL + KEYCODE

**KEYCODE Categories** (111 total):

1. **Balance Sheet (BS.*) - 31 items**
   - Selected balance sheet items from BS.1 - BS.171
   - **Note**: 138 BS.* items filtered out via `bs_skip.xlsx` (excluded from upload)
   - Filtered items include intermediate calculations, duplicate rollups, and non-essential line items

2. **Income Statement (IS.30) - 1 item**
   - IS.30: Provision for losses from mortgage assets

3. **Original Notes (NOS101-110) - 4 items**
   | KEYCODE | Description |
   |---------|-------------|
   | Institution_shares_trading_value | Institution shares trading volume |
   | Institution_bond_trading_value | Institution bond trading volume |
   | Investor_shares_trading_value | Investor shares trading volume |
   | Investor_bond_trading_value | Investor bond trading volume |

4. **fiin_notes (NOS119-465) - 46 items**
   - **Note**: 1 item excluded: "7.3.3. Investment Fund Certificates" (filtered via bs_skip.xlsx)

   **Cost of Financial Investment (7.x series)**:
   | KEYCODE | Description |
   |---------|-------------|
   | 7. Cost of the financial investment | Total cost |
   | 7.1. Short-term investments | FVTPL short-term |
   | 7.1.1. Trading Securities | Trading portfolio cost |
   | 7.1.1.1. Listed Shares | Listed equity cost |
   | 7.1.1.2. Unlisted Shares | Unlisted equity cost |
   | 7.1.1.3. Fund | Investment fund cost |
   | 7.1.1.4. Bonds | Bond cost (FVTPL) |
   | 7.1.2. Other short-term investments | Other FVTPL |
   | 7.2.1. Listed shares | AFS listed equity |
   | 7.2.2. Unlisted shares | AFS unlisted equity |
   | 7.2.3. Investment Fund Certificates | AFS funds |
   | 7.2.4. Bonds | AFS bonds |
   | 7.2.5. Monetary market instrument | AFS money market |
   | 7.3.1. Listed shares | HTM listed equity |
   | 7.3.2. Unlisted shares | HTM unlisted equity |
   | 7.3.3. Investment Fund Certificates | HTM funds |
   | 7.3.4. Bonds | HTM bonds |
   | 7.3.5. Monetary market instrument | HTM money market |

   **Market Value of Financial Investment (8.x series)**:
   | KEYCODE | Description |
   |---------|-------------|
   | 8. Market value of financial investment | Total market value |
   | 8.1. Long-term financial investment | FVTPL fair value |
   | 8.1.1. Trading Securities | Trading portfolio FV |
   | 8.1.1.1. Listed Shares | Listed equity FV |
   | 8.1.1.2. Unlisted Shares | Unlisted equity FV |
   | 8.1.1.3. Fund | Fund FV (FVTPL) |
   | 8.1.1.4. Bonds | Bond FV (FVTPL) |
   | 8.1.2. Other short-term investments | Other FVTPL FV |
   | 8.2.1. Listed shares | AFS listed FV |
   | 8.2.2. Unlisted shares | AFS unlisted FV |
   | 8.2.3. Investment Fund Certificates | AFS funds FV |
   | 8.2.5. Bonds | AFS bonds FV |
   | 8.5.1.1. Listed Shares | Long-term listed FV |
   | 8.5.1.2. Unlisted Shares | Long-term unlisted FV |
   | 8.5.1.3. Fund | Long-term fund FV |
   | 8.5.1.4. Bonds | Long-term bond FV |

5. **Calculated Metrics - 29 items**

   **Base Income & Profitability Metrics (23)**:
   | KEYCODE | Description | Formula/Source |
   |---------|-------------|----------------|
   | IS.1 | Operating Sales | IS.1 |
   | IS.41 | Cost of Sales | IS.44 |
   | Net_Brokerage_Income | Net Brokerage Income | IS.10 + IS.33 |
   | Net_IB_Income | Investment Banking Income | IS.12+13+15+11+16+17+18+34+35+36+38 |
   | Net_Trading_Income | Trading Income | IS.3+4+5+8+9+27+24+25+26+28+29+31+32 |
   | Net_Interest_Income | Interest Income | IS.6 |
   | Net_Margin_lending_Income | Margin Lending Income | IS.7 + IS.30 |
   | Net_other_operating_income | Other Operating Income | IS.14+19+20+37+39+40 |
   | Net_Other_Income | Other Income | IS.52+54+63 |
   | Net_Fee_Income | Fee Income | Brokerage + IB + Other Op |
   | Net_Capital_Income | Capital Income | Trading + Interest + Margin |
   | Net_investment_income | Net Investment Income | Trading + Interest |
   | Total_Operating_Income | Total Operating Income | Capital + Fee Income |
   | FX_Income | FX Gain/Loss | IS.44 + IS.50 |
   | Affiliates_Divestment | Affiliates Divestment | IS.46 |
   | Associate_Income | Associate Income | IS.47 + IS.55 |
   | Deposit_Income | Deposit Income | IS.45 |
   | Interest_Expense | Interest Expense | IS.51 |
   | SG_A | SG&A | IS.57 + IS.58 |
   | PBT | Profit Before Tax | IS.65 |
   | NPAT | Net Profit After Tax | IS.71 |
   | Borrowing_Balance | Borrowing Balance | BS.95+100+122+127 |
   | Margin_Lending_book | Margin Balance | BS.8 |

   **Ratio Metrics (6)**:
   | KEYCODE | Description | Formula | Typical Range |
   |---------|-------------|---------|---------------|
   | NET_BROKERAGE_FEE | Net Brokerage Fee (bps) | (Net_Brokerage / Trading_Value) × 10000 | 5-15 bps |
   | ROE | Return on Equity (annualized) | (NPAT / Equity) × 100 × 4 (if quarterly) | 10-25% |
   | ROA | Return on Assets (annualized) | (NPAT / Assets) × 100 × 4 (if quarterly) | 1-5% |
   | MARGIN_EQUITY_RATIO | Margin to Equity Ratio | (Margin_Balance / Equity) × 100 | 20-80% |
   | INTEREST_RATE | Borrowing Interest Rate (annualized) | (Interest_Expense / Avg_Borrowing) × 4 (if quarterly) | 5-10% |
   | MARGIN_LENDING_RATE | Margin Lending Rate (annualized) | (Margin_Income / Avg_Margin_Balance) × 100 × 4 (if quarterly) | 8-15% |

**Data Format**: Long format (KEYCODE in rows)
```
TICKER | ORGANCODE | YEARREPORT | LENGTHREPORT | ACTUAL | QUARTER_LABEL | KEYCODE | KEYCODE_NAME | VALUE
-------|-----------|------------|--------------|--------|---------------|---------|--------------|-------
SSI    | SSI       | 2024       | 1            | 1      | 1Q24          | BS.1    | CURRENT ASSETS | 5000000000
SSI    | SSI       | 2024       | 1            | 1      | 1Q24          | PBT     | PBT           | 500000000
SSI    | SSI       | 2024       | 1            | 1      | 1Q24          | 7.1.1.4. Bonds | 7.1.1.4. Bonds | 300000000
SSI    | SSI       | 2025       | 5            | 0      | 2025          | PBT     | PBT           | 550000000
```

**Special TICKER Values**:
- Individual brokers: SSI, VND, HCM, VCI, MBS, etc. (~30 firms)
- 'Sector': Aggregate of all securities firms

**QUARTER_LABEL Format**:
- Quarterly: `xQxx` format (e.g., `1Q24`, `2Q25`, `4Q23`)
- Annual: `YYYY` format (e.g., `2024`, `2025`)
- Derived from: LENGTHREPORT < 5 → `{LENGTHREPORT}Q{YY}`, else `{YEARREPORT}`

**ACTUAL Flag**:
- **1 (True)**: Historical data from actual financial statements
- **0 (False)**: Forecast data from analyst projections (LENGTHREPORT = 5, annual only)

**Output Statistics**:
- ~30 brokers tracked
- 2017-2024 (8 years) + forecast years (2025-2026)
- 5 periods per year (Q1-Q4 + Annual)
- ~250 KEYCODEs per broker-period (244 base + 6 ratio metrics)
- Actual data: ~292,800 rows
- Forecast data: Variable (depends on coverage)
- Total: ~350,000+ rows (actual + forecast + sector aggregates)

**Data Quality Notes**:
- NULL values removed during transformation
- VALUE column is numeric only
- KEYCODE preserves hierarchical numbering (e.g., 7.1.1.4 vs 7.2.4) to avoid duplicates
- All BS.*, IS.*, Notes columns transformed from wide to long format
- Sector aggregates calculated by summing numeric columns across all brokers
- **Forecast Data Filtering**: External broker forecasts excluded via SQL filters:
  - Excluded: `KEYCODE LIKE '%.NPATMI'` (other brokers' NPATMI forecasts)
  - Excluded: `KEYCODE LIKE '%.Target_Price'` (other brokers' price targets)
  - Only internal company forecasts included in pipeline

**Related Tables**:
- MarketTurnover: Market statistics by year (derived from S_SPS_HOSEINDEX)

---

### MarketTurnover
**Purpose**: HOSE market turnover statistics by year
**Update Frequency**: Quarterly/Annual (optional - disabled by default)
**Data Range**: 2017 - Present
**Row Count**: ~8 years
**Status**: **Optional** - Not calculated by default in pipeline

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **Year** | INT | NO | Calendar year | 2024 |
| trading_days | INT | YES | Number of trading days | 245 |
| total_turnover | FLOAT | YES | Total value traded (VND) | 5.67E+15 |
| avg_daily_turnover | FLOAT | YES | Average daily turnover | 2.31E+13 |

**Primary Key**: Year

**Calculation**:
- Extracted from S_SPS_HOSEINDEX table
- trading_days = COUNT(DISTINCT TRADINGDATE) per year
- total_turnover = SUM(TOTALVALUE) per year
- avg_daily_turnover = total_turnover / trading_days

**Pipeline Configuration**:
- **Default**: Market turnover calculation **disabled** (`include_market_turnover=False`)
- **Enable**: Use `--market-turnover` flag when running brokerage pipeline
- **Reason**: Reduces unnecessary database queries when turnover data not needed

---

## Reference Data Tables

### Forecast
**Purpose**: Master forecast data from IRIS system for all companies
**Update Frequency**: Weekly
**Data Range**: Current year + 2 years (e.g., 2025-2027)
**Row Count**: Variable (depends on coverage and projection horizon)

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **TICKER** | NVARCHAR(50) | NO | Stock symbol | 'VCB' |
| **KEYCODE** | NVARCHAR(50) | NO | Forecast metric identifier | 'Customer_loan' |
| **DATE** | INT | NO | Forecast year | 2025 |
| KEYCODENAME | NVARCHAR(200) | YES | Human-readable metric name | 'Customer Loans' |
| ORGANCODE | NVARCHAR(50) | YES | Organization code | 'VCB' |
| VALUE | FLOAT | YES | Projected metric value | 1500000000000 |
| RATING | NVARCHAR(20) | YES | Analyst rating | 'Buy', 'Hold', 'Sell' |
| FORECASTDATE | DATETIME | YES | Date projection was made | '2025-01-15' |

**Primary Key**: TICKER + KEYCODE + DATE

**Source**: `SIL.W_F_IRIS_FORECAST` table (Azure Synapse)

**KEYCODE Examples**:
- Banking: Customer_loan, CASA, LDR, NPL
- Financial Statement: Net_Revenue, EBITDA, NPAT
- Balance Sheet: Total_Asset, Total_Equity

**Usage**:
- Banking forecast processing uses this table to derive BS.XX, IS.XX metrics via equation solver
- Merged with historical data for forecasted BankingMetrics (ACTUAL=0)
- Provides analyst projections for financial modeling

**Data Quality Notes**:
- Annual projections only (no quarterly forecasts)
- Some metrics are high-level aggregates requiring formula decomposition
- RATING field may be NULL for non-equity research forecasts

---

### Sector_Map
**Purpose**: Master reference for ticker classification and index membership
**Update Frequency**: As needed
**Data Range**: All listed tickers
**Row Count**: 433

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| OrganCode | NVARCHAR(20) | YES | Organization code | 'VNMILK' |
| **Ticker** | NVARCHAR(10) | NO | Stock ticker | 'VNM' |
| ExportClassification | NVARCHAR(10) | YES | Export flag | 'Export' |
| Sector | NVARCHAR(20) | NO | Primary sector | 'Consumer' |
| L1 | NVARCHAR(30) | NO | Level 1 industry | 'Consumer Staples' |
| L2 | NVARCHAR(25) | NO | Level 2 industry | 'Food & Beverage' |
| L3 | NVARCHAR(25) | YES | Level 3 sub-industry | 'Dairy' |
| VNI | NVARCHAR(1) | YES | VN30 Index member | 'Y' or NULL |

**Primary Key**: Ticker

**Sector Distribution**:
- Consumer: ~100 tickers
- Industrial: ~150 tickers
- Service: ~80 tickers
- Financial: ~40 tickers
- Resources: ~60 tickers

**VNI Membership**: 37 tickers marked with 'Y'

---

## Economic Data Tables

### Monthly_Income
**Purpose**: Vietnam monthly income per salaried worker by geographic region
**Update Frequency**: Quarterly (one-off upload, historical data)
**Data Range**: 2015Q1 - 2025Q3
**Row Count**: 43

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **Year** | INT | NO | Calendar year | 2024 |
| **Quarter** | INT | NO | Quarter number (1-4) | 3 |
| Urban | FLOAT | YES | Monthly income in urban areas (VND mn) | 9.254 |
| Rural | FLOAT | YES | Monthly income in rural areas (VND mn) | 6.597 |
| Nationwide | FLOAT | YES | Monthly income nationwide average (VND mn) | 7.626 |

**Primary Key**: Year + Quarter

**Data Source**: Excel file (`data/monthly_income.xlsx`)

**Unit of Measure**: VND million per month per salaried worker

**Geographic Coverage**:
- **Urban**: Metropolitan and city areas
- **Rural**: Countryside and agricultural regions
- **Nationwide**: Weighted average across all regions

**Upload Method**:
- One-off upload via `scripts/operational/upload_monthly_income.py`
- Reads Excel file (skips rows 1-3, column A)
- Extracts Year and Quarter from "Quarter ending" datetime column

**Data Characteristics**:
- Complete quarterly coverage from 2015Q1 onwards
- Income values in millions of VND (e.g., 9.254 = 9,254,000 VND/month)
- Rural income consistently lower than urban (typically 70-75% of urban)
- Nationwide is weighted average, not simple mean
- Shows steady growth trend: ~5 VND mn (2015) → ~10 VND mn (2025)

**Query Example**:
```sql
-- Income growth trend by region
SELECT Year, Quarter,
       Urban, Rural, Nationwide,
       (Urban - Rural) as Urban_Rural_Gap
FROM Monthly_Income
WHERE Year >= 2020
ORDER BY Year, Quarter

-- Year-over-year comparison
SELECT
    curr.Year,
    curr.Quarter,
    curr.Nationwide as Current_Income,
    prev.Nationwide as YoY_Income,
    ((curr.Nationwide - prev.Nationwide) / prev.Nationwide * 100) as YoY_Growth_Pct
FROM Monthly_Income curr
LEFT JOIN Monthly_Income prev
    ON curr.Year = prev.Year + 1
    AND curr.Quarter = prev.Quarter
WHERE curr.Year >= 2016
ORDER BY curr.Year, curr.Quarter
```

---

### Container_volume
**Purpose**: Monthly container throughput data by port, company, and region for logistics analysis
**Update Frequency**: Monthly (via Excel file upload through portal)
**Data Range**: 2020 - Present
**Row Count**: ~1,750+ (growing monthly)

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **Date** | DATE | NO | Month date (first day of month) | '2025-08-01' |
| **Region** | NVARCHAR(50) | NO | Geographic region | 'Northern', 'Central', 'Southern' |
| **Company** | NVARCHAR(50) | NO | Operating company code | 'PHP', 'SNP', 'VSC' |
| **Port** | NVARCHAR(100) | NO | Port name | 'Hai Phong (Chùa Vẽ+Tân Vũ)' |
| Total throughput | FLOAT | YES | Container volume (TEU or similar unit) | 121727.0 |

**Primary Key**: Date + Region + Company + Port (Composite)

**Data Source**: Excel file uploaded via Container Volume Portal (🚢)

**Upload Method**:
- Batch upload via `writeoff_portal/portal_container_volume.py`
- Users upload Excel file with required columns
- System validates structure, detects duplicates, shows new records for confirmation
- Automatic duplicate detection prevents re-insertion of existing data

**Geographic Coverage**:
- **Northern**: Ports in northern Vietnam (Hai Phong area)
- **Central**: Ports in central Vietnam (Da Nang, Quy Nhon)
- **Southern**: Ports in southern Vietnam (Ho Chi Minh City area, Cai Mep-Thi Vai)

**Data Characteristics**:
- Complete monthly coverage from 2020 onwards
- Multiple ports operated by various companies in each region
- Throughput values represent container volume (typically in TEUs)
- Northern region typically has 10-12 port entries per month
- Central region typically has 1-2 port entries per month
- Southern region typically has 15-20 port entries per month
- Total monthly records: ~30 entries

**Portal Access**:
- Managed through **Container Volume Portal** in writeoff_portal application
- User-based access control via `user_permissions` configuration
- Excel file upload with real-time validation
- Shows latest month data automatically
- Prevents duplicate uploads with smart detection

**Query Examples**:
```sql
-- Latest month summary by region
SELECT
    Date,
    Region,
    COUNT(*) as PortCount,
    SUM([Total throughput]) as TotalThroughput
FROM Container_volume
WHERE Date = (SELECT MAX(Date) FROM Container_volume)
GROUP BY Date, Region
ORDER BY Region

-- Year-over-year throughput comparison
SELECT
    curr.Region,
    curr.Date as CurrentMonth,
    SUM(curr.[Total throughput]) as CurrentThroughput,
    SUM(prev.[Total throughput]) as YoYThroughput,
    ((SUM(curr.[Total throughput]) - SUM(prev.[Total throughput]))
        / SUM(prev.[Total throughput]) * 100) as YoY_Growth_Pct
FROM Container_volume curr
LEFT JOIN Container_volume prev
    ON curr.Region = prev.Region
    AND curr.Company = prev.Company
    AND curr.Port = prev.Port
    AND DATEADD(YEAR, 1, prev.Date) = curr.Date
WHERE curr.Date >= '2024-01-01'
GROUP BY curr.Region, curr.Date
ORDER BY curr.Date, curr.Region

-- Company market share by region
SELECT
    Date,
    Region,
    Company,
    SUM([Total throughput]) as CompanyThroughput,
    SUM(SUM([Total throughput])) OVER (PARTITION BY Date, Region) as RegionTotal,
    (SUM([Total throughput]) / SUM(SUM([Total throughput])) OVER (PARTITION BY Date, Region) * 100) as MarketShare_Pct
FROM Container_volume
WHERE Date >= '2025-01-01'
GROUP BY Date, Region, Company
ORDER BY Date, Region, MarketShare_Pct DESC

-- Port performance trend (monthly)
SELECT
    Date,
    Port,
    [Total throughput],
    LAG([Total throughput], 1) OVER (PARTITION BY Port ORDER BY Date) as PrevMonth,
    (([Total throughput] - LAG([Total throughput], 1) OVER (PARTITION BY Port ORDER BY Date))
        / LAG([Total throughput], 1) OVER (PARTITION BY Port ORDER BY Date) * 100) as MoM_Growth_Pct
FROM Container_volume
WHERE Company = 'VSC'
ORDER BY Date DESC, [Total throughput] DESC
```

---

## Table Relationships

### Primary Relationships
```
FA_Quarterly/FA_Annual
    ↓ [TICKER]
Sector_Map ← [TICKER] → MarketCap
    ↓ [TICKER]           ↓ [TICKER]
Market_Data ← [TICKER] → BankingMetrics
                         ↓ [TICKER, DATE]
                    Banking_Drivers (auto-calculated)
                         ↓ [TICKER]
                    Banking_Comments
                         ↓ [TICKER]
                    Bank_Writeoff (user-maintained)
```

### Banking Data Flow
```
Source Databases
    ↓
BankingMetrics (CA.1-26)
    ↓ [in-memory transformation]
Banking_Drivers (PBT decomposition)
    ↓
Target Database (parallel upload)
```

### Key Relationships
1. **TICKER** is the universal join key across all tables
2. **DATE** formats vary by table:
   - Financial: 'YYYYQX' or 'YYYY'
   - Banking: YEARREPORT + LENGTHREPORT
   - Banking_Drivers: 'YYYY-QX' or 'YYYY'
   - Bank_Writeoff: 'QXYYYY'
   - Market: DATETIME
3. **Sector_Map** provides classification for all tickers
4. **BankingMetrics** includes both individual banks and aggregates
5. **Banking_Drivers** is auto-calculated from BankingMetrics during pipeline runs
6. **Bank_Writeoff** is user-maintained and feeds into BankingMetrics calculations (CA.22-25)

---

## Data Update Patterns

### Daily Updates
- **MarketCap**: Full replacement with latest snapshot
- **Valuation**: Incremental addition of new trading day
- **MarketIndex**: Incremental addition of new trading day

### Weekly Updates
- **FA_Quarterly**: Incremental update for reporting companies
- **FA_Annual**: Incremental update (mainly during annual reporting season)

### Quarterly Updates
- **BankingMetrics**: Incremental update with smart deduplication
- **Banking_Drivers**: Auto-calculated during banking pipeline run
- **Bank_Writeoff**: Manual update by users (Excel upload or SQL)
- **Banking_Comments**: Manual updates as analysis completed

### Annual Updates
- **BankingMetrics (Forecast)**: Forecast data refresh with ACTUAL=0
- Updates when new analyst projections available
- Processed through equation solver for complex formulas

### Monthly Updates
- **Container_volume**: Excel file upload via Container Volume Portal
  - User-initiated batch upload through writeoff_portal application
  - Automatic duplicate detection and validation
  - Typically updated once per month with latest throughput data

### On-Demand Updates
- **Sector_Map**: When new listings or reclassifications occur
- **Forecast Data**: Can be updated as new projections become available
- **Monthly_Income**: One-off historical data upload (rarely updated)

---

## Query Examples

### 1. Get latest financials for a ticker
```sql
SELECT KEYCODE, VALUE, YoY
FROM FA_Quarterly
WHERE TICKER = 'VNM'
  AND DATE = (SELECT MAX(DATE) FROM FA_Quarterly WHERE TICKER = 'VNM')
ORDER BY KEYCODE
```

### 2. Banking peer comparison
```sql
SELECT TICKER, BANK_TYPE,
       [LDR] as LoanDeposit,
       [NPL] as NPL_Ratio,
       [ROE] as ReturnEquity
FROM BankingMetrics
WHERE YEARREPORT = 2024 AND LENGTHREPORT = 2
  AND TICKER IN ('VCB', 'CTG', 'BID', 'TCB', 'MBB')
ORDER BY [ROE] DESC
```

### 3. Sector performance overview
```sql
SELECT s.Sector,
       COUNT(DISTINCT m.TICKER) as StockCount,
       AVG(m.CUR_MKT_CAP) as AvgMarketCap
FROM Sector_Map s
JOIN MarketCap m ON s.Ticker = m.TICKER
GROUP BY s.Sector
ORDER BY AvgMarketCap DESC
```

### 4. VN30 Index members valuation
```sql
SELECT s.Ticker, s.L1, m.PE, m.PB, m.EV_EBITDA
FROM Sector_Map s
JOIN Market_Data m ON s.Ticker = m.TICKER
WHERE s.VNI = 'Y'
  AND m.TRADE_DATE = (SELECT MAX(TRADE_DATE) FROM Market_Data)
ORDER BY m.PE
```

### 5. Banking earnings quality analysis
```sql
-- VCB quarterly earnings drivers (T12M comparison)
SELECT TICKER, DATE, PBT, [PBT_Growth_%],
       Top_Line_Impact, Cost_Cutting_Impact, Non_Recurring_Impact
FROM Banking_Drivers
WHERE TICKER = 'VCB' AND PERIOD_TYPE = 'Q'
ORDER BY DATE DESC

-- Compare multiple comparison types
SELECT TICKER, DATE,
       Top_Line_Impact AS T12M_TopLine,
       Top_Line_Impact_QoQ AS QoQ_TopLine,
       Top_Line_Impact_YoY AS YoY_TopLine
FROM Banking_Drivers
WHERE TICKER = 'VCB' AND DATE = '2024-Q1'

-- Sector-level trends
SELECT DATE, Top_Line_Impact, Cost_Cutting_Impact, [PBT_Growth_%]
FROM Banking_Drivers
WHERE TICKER = 'Sector' AND PERIOD_TYPE = 'Y'
ORDER BY DATE
```

### 6. Banking metrics with earnings quality
```sql
-- Combined view: metrics + earnings analysis
SELECT
    bm.TICKER,
    bm.DATE_STRING,
    bm.PBT,
    bm.[ROE],
    bm.[NPL],
    bd.Top_Line_Impact,
    bd.Cost_Cutting_Impact,
    bd.[PBT_Growth_%]
FROM BankingMetrics bm
LEFT JOIN Banking_Drivers bd
    ON bm.TICKER = bd.TICKER
    AND bm.DATE_STRING = bd.DATE
    AND bd.PERIOD_TYPE = 'Q'
WHERE bm.YEARREPORT = 2024
  AND bm.LENGTHREPORT = 1
  AND bm.ACTUAL = 1
ORDER BY bm.PBT DESC
```

### 7. Brokerage metrics - key performance indicators
```sql
-- Get PBT and key income components for major brokers (actual data)
SELECT TICKER, QUARTER_LABEL, KEYCODE_NAME, VALUE
FROM BrokerageMetrics
WHERE TICKER IN ('SSI', 'VND', 'HCM', 'VCI', 'MBS')
  AND YEARREPORT = 2024
  AND LENGTHREPORT = 1
  AND ACTUAL = 1  -- Historical data only
  AND KEYCODE IN ('PBT', 'Net_Fee_Income', 'Net_Capital_Income', 'Total_Operating_Income')
ORDER BY TICKER, KEYCODE

-- Compare actual vs forecast for a broker
SELECT
    YEARREPORT,
    CASE WHEN ACTUAL = 1 THEN 'Actual' ELSE 'Forecast' END as DataType,
    KEYCODE_NAME,
    VALUE
FROM BrokerageMetrics
WHERE TICKER = 'SSI'
  AND LENGTHREPORT = 5  -- Annual data
  AND YEARREPORT IN (2024, 2025)
  AND KEYCODE IN ('PBT', 'ROE', 'ROA')
ORDER BY KEYCODE, YEARREPORT, ACTUAL DESC
```

### 8. Brokerage investment portfolio breakdown
```sql
-- Detailed investment portfolio analysis for a broker
SELECT
    QUARTER_LABEL,
    KEYCODE_NAME,
    VALUE / 1000000000 as Value_Billion_VND
FROM BrokerageMetrics
WHERE TICKER = 'SSI'
  AND YEARREPORT = 2024
  AND LENGTHREPORT = 1
  AND ACTUAL = 1  -- Historical data
  AND (KEYCODE LIKE '7.%' OR KEYCODE LIKE '8.%')  -- Cost and market value
ORDER BY KEYCODE
```

### 9. Brokerage sector aggregate comparison
```sql
-- Compare individual brokers vs sector average
WITH SectorData AS (
    SELECT YEARREPORT, LENGTHREPORT, ACTUAL, KEYCODE, VALUE as SectorValue
    FROM BrokerageMetrics
    WHERE TICKER = 'Sector'
),
BrokerData AS (
    SELECT TICKER, YEARREPORT, LENGTHREPORT, ACTUAL, KEYCODE, VALUE as BrokerValue
    FROM BrokerageMetrics
    WHERE TICKER = 'SSI' AND LENGTHREPORT = 5  -- Annual data
)
SELECT
    b.TICKER,
    b.YEARREPORT,
    CASE WHEN b.ACTUAL = 1 THEN 'Actual' ELSE 'Forecast' END as DataType,
    b.KEYCODE,
    b.BrokerValue,
    s.SectorValue,
    (b.BrokerValue / NULLIF(s.SectorValue, 0)) * 100 as MarketShare_Pct
FROM BrokerData b
JOIN SectorData s
    ON b.YEARREPORT = s.YEARREPORT
    AND b.LENGTHREPORT = s.LENGTHREPORT
    AND b.ACTUAL = s.ACTUAL  -- Match actual vs forecast
    AND b.KEYCODE = s.KEYCODE
WHERE b.KEYCODE IN ('PBT', 'Total_Operating_Income', 'Net_Fee_Income')
ORDER BY b.YEARREPORT DESC, b.ACTUAL DESC, b.KEYCODE
```

---

## Data Quality Notes

### Common Data Patterns
- **NULL handling**: NULL values indicate data not available or not applicable
- **YoY calculations**: First year/quarter will have NULL YoY values
- **Banking aggregates**: TICKER values like 'SOCB' represent tier aggregates
- **Date formats**: Inconsistent across tables - use appropriate conversion

### Data Validation Rules
- All TICKER values should exist in Sector_Map
- Financial metrics should have consistent KEYCODEs
- Banking metrics CA.1-CA.26 follow specific calculation rules
- Ratios bounded by business logic (e.g., NPL typically < 5%)

### Known Limitations
- Historical data starts from 2016 (2017 for banking)
- Some companies may have incomplete quarterly data
- Banking metrics require auxiliary Excel files for full calculations
- Banking earnings drivers require 4+ quarters for T12M/YoY (first quarters NULL)
- Market data updated with 1-day lag

---

## Forecast Data Integration

### Overview
The BankingMetrics table supports both historical and forecast data, distinguished by the ACTUAL column:
- **ACTUAL = 1 (True)**: Historical data from actual financial statements
- **ACTUAL = 0 (False)**: Forecast data from analyst projections

### Forecast Data Source
Forecast data originates from `SIL.W_F_IRIS_FORECAST` table with the following characteristics:
- **Annual Only**: Forecast data has LENGTHREPORT = 5
- **Date Range**: Typically current year and next year (e.g., 2025-2026)
- **KEYCODE Mapping**: Uses IRIS_KEYCODE.csv to map human-readable codes to banking formulas

### Equation Solving
Forecast data often contains high-level metrics that require equation solving:

| Forecast KEYCODE | Formula | Resolution |
|------------------|---------|------------|
| Customer_loan | BS.13+BS.16 | Solver derives BS.16 if BS.13 known |
| CASA | (Nt.121+Nt.124+Nt.125)/Deposit | Complex calculation |
| LDR | Loan/Deposit | Derives Loan if Deposit known |

The pipeline includes an equation solver that:
1. Parses formulas with operations (+, -, *, /)
2. Builds systems of equations from available data
3. Iteratively solves for unknown banking metrics
4. Converts results to standard BS.XX, IS.XX format

### Query Examples with Forecast Data

#### Compare Actual vs Forecast
```sql
SELECT TICKER, YEARREPORT,
       CASE WHEN ACTUAL = 1 THEN 'Historical' ELSE 'Forecast' END as DataType,
       [ROA] as ROA, [ROE] as ROE, [NPL] as NPL_Ratio
FROM BankingMetrics
WHERE TICKER = 'VCB'
  AND YEARREPORT IN (2024, 2025)
ORDER BY YEARREPORT, ACTUAL DESC
```

#### Forecast Trend Analysis
```sql
SELECT TICKER, YEARREPORT,
       [Net Interest Income] as NII,
       [Loan] as TotalLoans,
       [LDR] as LoanDepositRatio
FROM BankingMetrics
WHERE ACTUAL = 0  -- Forecast only
  AND TICKER IN ('VCB', 'CTG', 'TCB')
ORDER BY TICKER, YEARREPORT
```

---

## Contact & Support
For questions about data definitions, calculations, or access:
- **General Documentation**: `.docs/` directory
- **Banking Sector**: `.docs/banking/README.md` (complete guide)
- **Schema Reference**: This file
- **Banking Calculations**: `sectors/banking/banking_processor.py` (CA.1-26)
- **Earnings Drivers**: `sectors/banking/earnings_driver.py` (PBT decomposition)

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| Sept 2024 | 1.0 | Initial schema documentation |
| Jan 2025 | 2.0 | Added Banking_Drivers and Bank_Writeoff tables |
| Jan 2025 | 2.1 | Added BrokerageMetrics and MarketTurnover tables (Brokerage Analytics) |
| Oct 2025 | 2.2 | Added Forecast table (IRIS forecast data) |
| Oct 2025 | 2.3 | Added Monthly_Income table (Economic Data) |
| Oct 2025 | 2.4 | Added Container_volume table (Logistics Data) - Monthly container throughput by port |
| Oct 2025 | 2.5 | **Updated BrokerageMetrics schema**: Added ACTUAL column, ORGANCODE column, 6 new ratio metrics (ROE, ROA, NET_BROKERAGE_FEE, MARGIN_EQUITY_RATIO, INTEREST_RATE, MARGIN_LENDING_RATE), forecast data integration, updated primary key to include ACTUAL flag, total KEYCODEs now 250 (244 base + 6 ratios) |

Last Updated: October 15, 2025