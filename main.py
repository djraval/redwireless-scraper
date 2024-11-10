import asyncio
import aiohttp
import json
from string import ascii_lowercase, digits
from itertools import product
from pathlib import Path

async def fetch_companies(session, search_term):
    """Return tuple of (result, error)"""
    url = "https://api.redwireless.ca/rpp/companies/list"
    try:
        async with session.get(url, params={"name": search_term}) as response:
            if response.status == 200:
                return await response.json(), None
            return None, f"HTTP {response.status} for search term '{search_term}'"
    except Exception as e:
        return None, f"Error with search term '{search_term}': {str(e)}"

async def fetch_company_details(session, company_id: str):
    """Return tuple of (result, error)"""
    url = f"https://api.redwireless.ca/rpp/companies/get/{company_id}"
    try:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json(), None
            return None, f"HTTP {response.status} for company ID '{company_id}'"
    except Exception as e:
        return None, f"Error with company ID '{company_id}': {str(e)}"

async def process_batch(session, terms):
    tasks = [fetch_companies(session, term) for term in terms]
    results = await asyncio.gather(*tasks)
    
    companies = []
    errors = []
    for term, (data, error) in zip(terms, results):
        if error:
            errors.append(error)
        elif data:
            companies.extend(data)
    
    return companies, errors

async def collect_all_companies(force_refresh: bool = False) -> list:
    """
    Step 1: Collect all companies from the API using various search patterns
    Returns list of companies
    """
    all_companies = set()
    all_errors = []
    
    # Generate search terms
    search_chars = ascii_lowercase + digits
    search_terms = (
        list(search_chars) +  # Single character
        [''.join(p) for p in product(search_chars, repeat=2)]  # Two characters
    )
    
    print(f"Starting company collection...")
    print(f"Total search terms to process: {len(search_terms)}")
    
    batch_size = 50
    batches = [search_terms[i:i + batch_size] for i in range(0, len(search_terms), batch_size)]
    
    connector = aiohttp.TCPConnector(limit=0)
    async with aiohttp.ClientSession(connector=connector) as session:
        for i, batch in enumerate(batches, 1):
            companies, errors = await process_batch(session, batch)
            previous_count = len(all_companies)
            for company in companies:
                all_companies.add(json.dumps(company))
            new_companies = len(all_companies) - previous_count
            print(f"Batch {i}/{len(batches)} completed. Added {new_companies} new companies. Total: {len(all_companies)}")
            all_errors.extend(errors)

    final_companies = [json.loads(company) for company in all_companies]
    
    print(f"\nCollection complete! Found {len(final_companies)} unique companies")
    
    return final_companies

async def enrich_company_data(companies: list, force_refresh: bool = False) -> list:
    """
    Step 2: Enrich company data with group information
    Returns enriched company data
    """
    print("\nStarting company data enrichment...")
    enriched_companies = []
    enrichment_errors = []
    
    connector = aiohttp.TCPConnector(limit=0)
    async with aiohttp.ClientSession(connector=connector) as session:
        batch_size = 50
        for i in range(0, len(companies), batch_size):
            batch = companies[i:i + batch_size]
            tasks = [fetch_company_details(session, company['id']) for company in batch]
            results = await asyncio.gather(*tasks)
            
            for company, (result, error) in zip(batch, results):
                if error:
                    enrichment_errors.append(error)
                elif result:
                    enriched_companies.append(result)
            
            print(f"Processed {min(i + batch_size, len(companies))}/{len(companies)} companies")

    if enrichment_errors:
        print("\nErrors during enrichment:")
        for error in enrichment_errors:
            print(f"- {error}")
    
    print(f"\nEnrichment complete!")
    print(f"Successfully enriched: {len(enriched_companies)} companies")
    print(f"Failed enrichments: {len(enrichment_errors)}")
    
    return enriched_companies

async def fetch_all_phones(session):
    """Return tuple of (phones_list, error)"""
    url = "https://api.redwireless.ca/rpp/phones/list"
    try:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('phones', []), None
            return None, f"HTTP {response.status} fetching phones list"
    except Exception as e:
        return None, f"Error fetching phones list: {str(e)}"

async def fetch_addons(session, company_id: str, group_id: str, phone_id: str, phone_model_id: str, plan_id: str):
    """Return tuple of (addons_list, error)"""
    url = "https://api.redwireless.ca/rpp/addons/list"
    params = {
        "companyId": company_id,
        "companyGroupsIds": group_id,
        "province": "ON",
        "customerType": "AAL",
        "customerLine": "Primary",
        "isSalesRep": "false",
        "phoneId": phone_id,
        "phoneModelId": phone_model_id,
        "planId": plan_id
    }
    
    try:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                return await response.json(), None
            return None, f"HTTP {response.status} fetching addons"
    except Exception as e:
        return None, f"Error fetching addons: {str(e)}"

async def fetch_phone_details(session, slug: str, group_id: str):
    """Return tuple of (phone_details, error)"""
    url = "https://api.redwireless.ca/rpp/phones/detail"
    params = {
        "slug": slug,
        "companyGroupsIds": group_id,
        "province": "ON",
        "customerLine": "Primary",
        "isSalesRep": "false"
    }
    
    try:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                details = await response.json()
                
                # Fetch addons for each model's plans
                if details and 'models' in details:
                    for model in details['models']:
                        if 'plans' in model:
                            addon_tasks = []
                            for plan in model['plans']:
                                addon_tasks.append(
                                    fetch_addons(
                                        session=session,
                                        company_id="",  # Not needed since we're using group_id
                                        group_id=group_id,
                                        phone_id=details.get('id', ''),
                                        phone_model_id=model.get('id', ''),  # Get model ID
                                        plan_id=plan.get('id', '')
                                    )
                                )
                            
                            # Fetch all addons concurrently
                            addon_results = await asyncio.gather(*addon_tasks)
                            
                            # Add addons to each plan
                            for plan, (addons, error) in zip(model['plans'], addon_results):
                                if not error and addons:
                                    plan['addons'] = addons
                                else:
                                    plan['addons'] = []
                
                return details, None
            return None, f"HTTP {response.status} for phone {slug}, group {group_id}"
    except Exception as e:
        return None, f"Error fetching phone details for {slug}: {str(e)}"

async def fetch_phones_list(session, company_id: str, group_id: str):
    """Return tuple of (phones_list, error)"""
    url = "https://api.redwireless.ca/rpp/phones/list"
    params = {
        "companyId": company_id,
        "companyGroupsIds": group_id,
        "province": "ON",
        "customerLine": "Primary",
        "isSalesRep": "false"
    }
    
    try:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('phones', []), None
            return None, f"HTTP {response.status} for company {company_id}, group {group_id}"
    except Exception as e:
        return None, f"Error fetching phones for company {company_id}, group {group_id}: {str(e)}"

def update_company_phones(company, phone_mapping):
    """Update company with phones from the mapping"""
    for group in company.get('groups', []):
        group['phones'] = phone_mapping.get((company['id'], group['id']), [])
    return company

async def collect_phones_data(enriched_companies: list, force_refresh: bool = False) -> list:
    """
    Step 3: Collect phones data for unique groups
    """
    print("\nStarting phones collection...")
    
    # Get unique groups with their associated companies
    unique_groups = {}
    for company in enriched_companies:
        for group in company.get('groups', []):
            if group['id'] not in unique_groups:
                unique_groups[group['id']] = {
                    'id': group['id'],
                    'company_group': group['name'],
                    'companies': [],
                    'phones': []
                }
            unique_groups[group['id']]['companies'].append(company['name'])
    
    print(f"Found {len(unique_groups)} unique groups")
    
    connector = aiohttp.TCPConnector(limit=0)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Step 1: Get master list of phones
        print("Fetching master list of phones...")
        phones_list, error = await fetch_phones_list(session, "", "")
        if error:
            print(f"Error fetching master phone list: {error}")
            return []
            
        print(f"Found {len(phones_list)} available phones")
        
        # Step 2: Get phone details for each group
        print("\nFetching phone details for each group...")
        collection_errors = []
        
        # Process groups in batches
        batch_size = 10
        group_batches = [list(unique_groups.keys())[i:i + batch_size] 
                        for i in range(0, len(unique_groups), batch_size)]
        
        for batch_num, group_batch in enumerate(group_batches, 1):
            tasks = []
            for group_id in group_batch:
                group_tasks = [
                    fetch_phone_details(session, phone['slug'], group_id)
                    for phone in phones_list
                ]
                tasks.extend(group_tasks)
            
            results = await asyncio.gather(*tasks)
            
            # Process results
            result_idx = 0
            for group_id in group_batch:
                for _ in phones_list:
                    details, error = results[result_idx]
                    if error:
                        collection_errors.append(error)
                    elif details:
                        unique_groups[group_id]['phones'].append(details)
                    result_idx += 1
            
            print(f"Processed {min((batch_num * batch_size), len(unique_groups))}/{len(unique_groups)} groups")
    
    # Sort and deduplicate companies list for each group
    for group in unique_groups.values():
        group['companies'] = sorted(set(group['companies']))

    # Save groups data
    print("\nSaving groups data...")
    groups_data = list(unique_groups.values())
    
    total_phones = sum(len(group['phones']) for group in unique_groups.values())
    print(f"\nPhone collection complete!")
    print(f"Groups processed: {len(unique_groups)}")
    print(f"Total unique phone listings: {total_phones}")
    print(f"Failed requests: {len(collection_errors)}")
    
    return groups_data

async def main():
    """Main orchestration function"""
    force_refresh = False
    
    # Step 1: Collect companies
    companies = await collect_all_companies(force_refresh=force_refresh)
    
    # Step 2: Enrich with company group IDs
    enriched_companies = await enrich_company_data(companies, force_refresh=force_refresh)
    
    # Step 3: Collect phones data
    groups_data = await collect_phones_data(enriched_companies, force_refresh=force_refresh)
    
    # Save final output
    output_file = Path('data/final_data.json')
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(groups_data, f, indent=2, ensure_ascii=False)
    print(f"\nSaved final data to {output_file}")
    
    # Statistics
    total_companies = sum(len(group['companies']) for group in groups_data)
    total_phones = sum(len(group['phones']) for group in groups_data)
    unique_phones = len(set(
        phone['slug']
        for group in groups_data
        for phone in group['phones']
    ))
    
    print(f"\nFinal Statistics:")
    print(f"Total unique groups: {len(groups_data)}")
    print(f"Total companies: {total_companies}")
    print(f"Total phone listings: {total_phones}")
    print(f"Unique phone models: {unique_phones}")
    
    # Sample output
    print("\nSample group data:")
    if groups_data:
        group = groups_data[0]
        print(f"\nGroup: {group['company_group']}")
        print(f"Companies: {len(group['companies'])} (showing first 3)")
        for company in group['companies'][:3]:
            print(f"- {company}")
        print(f"\nPhones: {len(group['phones'])} (showing first 3)")
        for phone in group['phones'][:3]:
            print(f"\n- {phone['brand']} {phone['name']} (Slug: {phone['slug']})")
            if 'models' in phone:
                for model in phone['models']:
                    print(f"  Model: {model.get('storage', 'N/A')}GB")
                    if 'plans' in model:
                        print("  Plans:")
                        for plan in model['plans'][:2]:  # Show first 2 plans
                            print(f"    - {plan['title']} (${plan['price']}/mo)")
                            if plan.get('addons'):
                                print("      Addons:")
                                for addon in plan['addons'][:2]:  # Show first 2 addons
                                    price_text = "FREE" if addon['isFree'] else f"${addon['price']}"
                                    print(f"        - {addon['name']} ({price_text})")

if __name__ == "__main__":
    asyncio.run(main())