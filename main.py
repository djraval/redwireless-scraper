import asyncio
import aiohttp
import json
from string import ascii_lowercase, digits
from itertools import product
from pathlib import Path
from datetime import datetime

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

async def collect_all_companies() -> list:
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

async def enrich_company_data(companies: list) -> list:
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

def update_company_phones(company, phone_mapping):
    """Update company with phones from the mapping"""
    for group in company.get('groups', []):
        group['phones'] = phone_mapping.get((company['id'], group['id']), [])
    return company

async def collect_master_phone_catalog(session) -> dict:
    """
    Collect and build a master catalog of all available phones
    Returns a dictionary of phones keyed by slug
    """
    print("\nBuilding master phone catalog...")
    
    # Get base phone list using fetch_all_phones instead
    phones_list, error = await fetch_all_phones(session)
    if error:
        print(f"Error fetching master phone list: {error}")
        return {}
    
    # Build master catalog with base details
    master_catalog = {}
    for phone in phones_list:
        master_catalog[phone['slug']] = {
            'base_details': phone,
            'models': {},  # Will store model details keyed by storage size
            'group_specific_data': {}  # Will store pricing by group ID
        }
    
    print(f"Added {len(master_catalog)} phones to master catalog")
    return master_catalog

async def collect_group_specific_pricing(session, master_catalog: dict, group_id: str):
    """
    Collect group-specific pricing for phones in the master catalog
    """
    collection_errors = []
    
    # Fetch details for each phone for this group
    tasks = [
        fetch_phone_details(session, slug, group_id)
        for slug in master_catalog.keys()
    ]
    
    results = await asyncio.gather(*tasks)
    
    # Process results
    for slug, (details, error) in zip(master_catalog.keys(), results):
        if error:
            collection_errors.append(error)
        elif details:
            master_catalog[slug]['group_specific_data'][group_id] = details
            
            # Update master catalog with any new model information
            if 'models' in details:
                for model in details['models']:
                    storage = model.get('storage')
                    if storage and storage not in master_catalog[slug]['models']:
                        master_catalog[slug]['models'][storage] = model
    
    return collection_errors

async def collect_phones_data(enriched_companies: list) -> list:
    """
    Step 3: Collect phones data for unique groups using master catalog
    Returns a list of group data with their phones
    """
    print("\nStarting phones collection...")
    
    # Get unique groups and create mapping
    unique_groups = {}
    group_company_mapping = {}  # New mapping dictionary
    for company in enriched_companies:
        for group in company.get('groups', []):
            group_id = group['id']
            if group_id not in unique_groups:
                unique_groups[group_id] = {
                    'group_id': group_id,  # Changed from 'id' to 'group_id'
                    'company_group': group['name'],
                    'phones': []
                }
                group_company_mapping[group_id] = {
                    'group_name': group['name'],
                    'companies': set([company['name']])
                }
            else:
                group_company_mapping[group_id]['companies'].add(company['name'])
    
    print(f"Found {len(unique_groups)} unique groups")
    
    connector = aiohttp.TCPConnector(limit=0)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Build master catalog
        master_catalog = await collect_master_phone_catalog(session)
        if not master_catalog:
            print("Error: Failed to build master phone catalog")
            return []
        
        # Collect group-specific pricing
        print("\nCollecting group-specific pricing...")
        all_errors = []
        
        batch_size = 10
        group_batches = [list(unique_groups.keys())[i:i + batch_size] 
                        for i in range(0, len(unique_groups), batch_size)]
        
        for batch_num, group_batch in enumerate(group_batches, 1):
            for group_id in group_batch:
                errors = await collect_group_specific_pricing(
                    session, 
                    master_catalog, 
                    group_id
                )
                all_errors.extend(errors)
            
            print(f"Processed {min((batch_num * batch_size), len(unique_groups))}/{len(unique_groups)} groups")
        
        if all_errors:
            print("\nErrors during group-specific pricing collection:")
            for error in all_errors[:5]:  # Show first 5 errors
                print(f"- {error}")
            if len(all_errors) > 5:
                print(f"... and {len(all_errors) - 5} more errors")
        
        # Build final output
        final_groups = []
        for group_id, group_data in unique_groups.items():
            group_phones = []
            for slug, phone_data in master_catalog.items():
                if group_id in phone_data['group_specific_data']:
                    group_phones.append(phone_data['group_specific_data'][group_id])
            
            final_groups.append({
                'group_id': group_data['group_id'],
                'company_group': group_data['company_group'],
                'phones': group_phones
            })
        
        print(f"\nSuccessfully processed {len(final_groups)} groups")
        print(f"Total phones collected: {sum(len(group['phones']) for group in final_groups)}")
        
        return final_groups, group_company_mapping

async def main():
    """Main orchestration function"""
    try:
        # Step 1: Collect companies
        companies = await collect_all_companies()
        if not companies:
            print("Error: No companies collected")
            return
        
        # Step 2: Enrich with company group IDs
        enriched_companies = await enrich_company_data(companies)
        if not enriched_companies:
            print("Error: No enriched company data")
            return
        
        # Step 3: Collect phones data
        groups_data, group_company_mapping = await collect_phones_data(enriched_companies)
        if not groups_data:
            print("Error: No groups data collected")
            return
        
        # Add timestamp before creating final_output
        timestamp = datetime.utcnow().isoformat()

        final_output = {
            "created_at": timestamp,
            "groups": []
        }

        for group in groups_data:
            group_id = group['group_id']
            mapping_data = group_company_mapping[group_id]
            
            # Create combined structure
            combined_group = {
                'group_id': group['group_id'],
                'company_group': group['company_group'],
                'companies': sorted(list(mapping_data['companies'])),
                'phones': group['phones']
            }
            final_output["groups"].append(combined_group)

        # Save single combined output
        output_file = Path('data/final_data.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, indent=2, ensure_ascii=False)
        print(f"Saved combined data to {output_file}")
        
        # Statistics
        total_companies = sum(len(group['companies']) for group in final_output['groups'])
        total_phones = sum(len(group['phones']) for group in final_output['groups'])
        unique_phones = len(set(
            phone['slug']
            for group in final_output['groups']
            for phone in group['phones']
        ))
        
        print(f"\nFinal Statistics:")
        print(f"Total unique groups: {len(final_output['groups'])}")
        print(f"Total companies: {total_companies}")
        print(f"Total phone listings: {total_phones}")
        print(f"Unique phone models: {unique_phones}")
        
        # Updated sample output
        print("\nSample group data:")
        if final_output['groups']:
            group = final_output['groups'][0]
            print(f"\nGroup ID: {group['group_id']}")
            print(f"Group Name: {group['company_group']}")
            
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
    
    except Exception as e:
        print(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())