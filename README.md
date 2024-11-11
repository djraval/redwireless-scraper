# RedWireless Phone Plan Scraper

A tool to collect and compare phone plan pricing across different company groups from RedWireless.

## ⚠️ Disclaimers

- This is an **unofficial** scraper created for educational and personal use only
- This project is not affiliated with, authorized, maintained, sponsored, or endorsed by RedWireless or any of its affiliates
- The data collected may not be 100% accurate or up-to-date
- Use this tool responsibly and at your own risk
- This project was created for fun and learning purposes only
- Please respect RedWireless's terms of service and rate limits when using this tool
- Consider checking RedWireless's official website or contacting them directly for the most accurate pricing and plan information

## Overview

This project consists of two main components:
1. **Data Collection** (`main.py`): Fetches and aggregates phone plan data from RedWireless
2. **Query Tool** (`query_phones.py`): Analyzes and compares phone plans across different company groups

### Key Concepts

- **Company Groups**: Groups (e.g., RPP, Lifeworks) that offer special pricing to their member companies
- **Plans**: Various data plans with different features and pricing across company groups
- **Add-ons**: Optional features that can be added to plans

## Setup & Usage

1. **Installation**
```bash
git clone https://github.com/djraval/redwireless-scraper.git
cd redwireless-scraper
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Data Collection**
```bash
python main.py
```

3. **Query Tool Usage**
```bash
# List available phones
python query_phones.py --list

# List available plans
python query_phones.py --list-plans

# Compare specific phone prices
python query_phones.py --phone-slug apple-iphone-15 --storage-size 128
```

## Technical Details

### API Endpoints

The scraper interacts with the following RedWireless API endpoints:

1. Company Listing:
   - Endpoint: `api.redwireless.ca/rpp/companies/list`
   - Purpose: Lists all companies with special pricing
   - Parameters: `name` (search term)

2. Company Details:
   - Endpoint: `api.redwireless.ca/rpp/companies/get/{company_id}`
   - Purpose: Gets detailed information about a specific company and its group

3. Phone Listing:
   - Endpoint: `api.redwireless.ca/rpp/phones/list`
   - Purpose: Gets the master list of all available phones

4. Phone Details:
   - Endpoint: `api.redwireless.ca/rpp/phones/detail`
   - Purpose: Gets detailed pricing for a specific phone
   - Parameters: 
     - `slug`: Phone model identifier
     - `companyGroupsIds`: Company group ID
     - `province`: Province code
     - Other parameters for customer type and line type

5. Add-ons Listing:
   - Endpoint: `api.redwireless.ca/rpp/addons/list`
   - Purpose: Lists available add-ons for a specific phone/plan combination
   - Parameters:
     - `companyId`: Company identifier
     - `companyGroupsIds`: Company group ID
     - `phoneId`: Phone model ID
     - `phoneModelId`: Specific model ID
     - `planId`: Plan identifier

### Data Collection (main.py)

The `main.py` script:
- Collects data about available phones, plans, and pricing from RedWireless
- Aggregates information across different company groups
- Stores the collected data in `data/final_data.json`
- Is designed to be run periodically (e.g., hourly via GitHub Actions)

### Query Tool (query_phones.py)

The `query_phones.py` script provides a command-line interface to analyze the collected data. It allows you to:
- List all available phones and their storage options
- List all available plans
- Compare prices for specific phone models across different company groups
- View detailed plan information including add-ons

## Examples

1. List all available phones:
```bash
python query_phones.py --list
```

Example output:
```
Available Phones:
================================================================================
Apple iPhone 15
  Slug: apple-iphone-15
  Storage Options: 128GB 256GB 512GB
--------------------------------------------------------------------------------
Samsung Galaxy S24
  Slug: samsung-galaxy-s24
  Storage Options: 128GB 256GB
...
```

2. List all available plans:
```bash
python query_phones.py --list-plans
```

Example output:
```
Available Plans:
================================================================================
Plan ID: a04862d6
  Infinite 5G Plan (65GB)
  Infinite 5G Plan (60GB)
--------------------------------------------------------------------------------
Plan ID: da3cf9ca
  CAN-US Infinite 5G Plan (100GB)
...
```

3. Compare prices for a specific phone:
```bash
python query_phones.py --phone-slug apple-iphone-15 --storage-size 128
```

This will show a detailed comparison including:
- Monthly prices across different company groups
- Upfront (Bring-It-Back) vs Financing options
- Total cost over 24 months
- Available add-ons for each plan
- The results are also saved to a JSON file in the data directory

### Output Files

When querying a specific phone, the script generates a JSON file with detailed information:
- Location: `data/<phone-slug>_<storage>gb_filtered.json`
- Contains full details about pricing, plans, and add-ons for the queried phone

### Notes

- The script uses data collected by `main.py` and stored in `data/final_data.json`
- Prices include the monthly plan cost
- The "Bring-It-Back" option requires returning the phone after 24 months or paying the buyout price
- Add-ons are available for most plans and their prices are shown separately
- Different company groups may have different pricing for the same plan
- Employees must verify their eligibility through their employer for special pricing

## Legal Notice

This is a personal project created for educational purposes. The creator(s) make no warranties about the completeness, reliability, and accuracy of the data provided. Any action you take upon the information from this project is strictly at your own risk. The creator(s) will not be liable for any losses and/or damages in connection with the use of this project.

All product names, logos, brands, trademarks and registered trademarks are property of their respective owners. All company, product and service names used in this project are for identification purposes only. Use of these names, trademarks and brands does not imply endorsement.
