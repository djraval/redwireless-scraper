import json
from pathlib import Path
from typing import List, Dict, Set, Tuple
from collections import defaultdict
import argparse

def load_data(file_path: str = 'data/final_data.json') -> List[Dict]:
    """Load the JSON data from file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def filter_phone_models(phone: Dict, storage: int) -> Dict:
    """Filter phone models by storage capacity"""
    if 'models' in phone:
        filtered_models = [
            model for model in phone['models']
            if model.get('storage') == storage
        ]
        if filtered_models:
            filtered_phone = phone.copy()
            filtered_phone['models'] = filtered_models
            return filtered_phone
    return None

def compare_plan_prices(results: List[Dict], sort_by: str = None, plan_id: str = None) -> Dict:
    """
    Compare plan prices across groups
    sort_by: 'upfront' or 'financing' to sort by price
    plan_id: optional filter for specific plan
    """
    plan_comparison = defaultdict(list)
    
    for group in results:
        group_id = group['group_id']
        group_name = group['company_group']
        
        if not group['phones'] or not group['phones'][0].get('models'):
            continue
            
        phone = group['phones'][0]
        model = phone['models'][0]  # We already filtered for specific storage
        
        for plan in model.get('plans', []):
            current_plan_id = plan['id']
            # Skip if plan_id is specified and doesn't match
            if plan_id and current_plan_id != plan_id:
                continue
                
            plan_title = plan['title']
            plan_data = plan.get('data', 'N/A')
            
            # Extract pricing details
            upfront = plan.get('upfront', {})
            upfront_price = upfront.get('priceAfterDiscount')
            buyout_price = upfront.get('buyoutPrice')
            financing_price = plan.get('financing', {}).get('priceAfterDiscount')
            monthly_price = plan.get('price')
            
            # Extract addons from the plan
            addons = plan.get('addons', [])
            
            plan_comparison[current_plan_id].append({
                'group_id': group_id,
                'group_name': group_name,
                'plan_title': plan_title,
                'plan_data': plan_data,
                'upfront_price': upfront_price,
                'buyout_price': buyout_price,
                'financing_price': financing_price,
                'monthly_price': monthly_price,
                'addons': addons  # Add the addons to the comparison data
            })
    
    # Sort the groups within each plan if requested
    if sort_by in ['upfront', 'financing']:
        for plan_id in plan_comparison:
            plan_comparison[plan_id].sort(
                key=lambda x: float('-inf') if x[f'{sort_by}_price'] is None 
                            else x[f'{sort_by}_price']
            )
    
    return plan_comparison

def calculate_total_costs(upfront_price: float, buyout_price: float, financing_price: float, monthly_price: float) -> tuple:
    """Calculate total costs for both upfront and financing options over 24 months"""
    if None in (upfront_price, buyout_price, financing_price, monthly_price):
        return None, None
        
    # Total device cost (excluding plan)
    upfront_total = round((upfront_price * 24) + buyout_price - (monthly_price * 24), 2)
    financing_total = round((financing_price * 24) - (monthly_price * 24), 2)
    
    return upfront_total, financing_total

def print_price_comparison(plan_comparison: Dict, phone_name: str, upfront_display_name: str = "Upfront"):
    """Print formatted price comparison"""
    # Define column widths
    GROUP_COL_WIDTH = 35
    PRICE_COL_WIDTH = 30
    TOTAL_WIDTH = 110
    
    print(f"\nPrice Comparison for {phone_name}:")
    print("="*TOTAL_WIDTH)
    
    # Track if this is the first plan
    first_plan = True
    
    for plan_id, groups in plan_comparison.items():
        # Add extra spacing between plans (except for the first one)
        if not first_plan:
            print("\n" + "="*TOTAL_WIDTH + "\n")
        first_plan = False
        
        plan_title = groups[0]['plan_title']
        plan_data = groups[0]['plan_data']
        monthly_price = groups[0]['monthly_price']
        
        # Print header with bundled cost note
        header = f"Plan: {plan_title} ({plan_data}GB) - ${monthly_price}/mo (ID: {plan_id})"
        print(header)
        print(f"Note: All prices below include the ${monthly_price}/mo plan cost")
        print("-"*TOTAL_WIDTH)
        
        # Column headers
        print(f"{'Group Name':<{GROUP_COL_WIDTH}} {upfront_display_name:<{PRICE_COL_WIDTH}} {'Financing':<{PRICE_COL_WIDTH}}")
        print("-"*TOTAL_WIDTH)
        
        # Print group prices
        for group in groups:
            group_name = group['group_name']
            upfront_price = group['upfront_price']
            buyout_price = group['buyout_price']
            financing_price = group['financing_price']
            
            # Format the prices
            upfront = f"${upfront_price}/mo (buyout: ${buyout_price})" if upfront_price is not None else "N/A"
            financing = f"${financing_price}/mo" if financing_price is not None else "N/A"
            upfront_total = f"24 Payments: ${upfront_price * 24}" if upfront_price is not None else ""
            financing_total = f"24 Payments: ${financing_price * 24}" if financing_price is not None else ""
            
            # Print the main row and totals
            print(f"{group_name:<{GROUP_COL_WIDTH}} {upfront:<{PRICE_COL_WIDTH}} {financing:<{PRICE_COL_WIDTH}}")
            print(f"{'':<{GROUP_COL_WIDTH}} {upfront_total:<{PRICE_COL_WIDTH}} {financing_total:<{PRICE_COL_WIDTH}}")
            
        # Add separator line after the last group in each plan
        print("-"*TOTAL_WIDTH)
        
        # Print available addons for this plan
        if 'addons' in groups[0]:
            print("\nAvailable Add-ons:")
            print("-" * 50)
            for addon in groups[0]['addons']:
                name = addon['name'].rstrip(' -')  # Remove trailing dash if present
                price = addon['price']
                is_free = addon.get('isFree', False)
                
                if is_free:
                    print(f"🎁 {name} - FREE!")
                else:
                    print(f"• {name} - ${price}/mo")
            print("-" * 50)

def find_phone_by_slug_and_storage(data: List[Dict], phone_slug: str, storage: int) -> List[Dict]:
    """
    Find all instances of a phone by its slug and storage capacity across all groups
    Returns a list of filtered group data containing only the specified phone and storage
    """
    filtered_groups = []
    
    for group in data:
        matching_phones = [
            phone for phone in group['phones']
            if phone['slug'] == phone_slug
        ]
        
        if matching_phones:
            filtered_phone = filter_phone_models(matching_phones[0], storage)
            
            if filtered_phone:
                filtered_group = {
                    'group_id': group['group_id'],
                    'company_group': group['company_group'],
                    'companies': group['companies'],
                    'phones': [filtered_phone]
                }
                filtered_groups.append(filtered_group)
    
    return filtered_groups

def get_available_phones(data: List[Dict]) -> List[Tuple[str, str, Set[int]]]:
    """Get all available phones and their storage options across all groups"""
    phone_options = {}
    
    for group in data:
        for phone in group['phones']:
            slug = phone['slug']
            name = f"{phone['brand']} {phone['name']}"
            
            if 'models' in phone:
                storage_options = {model['storage'] for model in phone['models'] if 'storage' in model}
                
                if slug in phone_options:
                    phone_options[slug][1].update(storage_options)
                else:
                    phone_options[slug] = (name, storage_options)
    
    # Convert to sorted list of tuples (slug, name, storage_options)
    return [(slug, name, sorted(storage)) for slug, (name, storage) in sorted(phone_options.items())]

def print_available_phones(phones: List[Tuple[str, str, Set[int]]]):
    """Print all available phones and their storage options"""
    print("\nAvailable Phones:")
    print("=" * 80)
    for slug, name, storage_options in phones:
        storage_str = ", ".join(f"{size}GB" for size in storage_options)
        print(f"{name}")
        print(f"  Slug: {slug}")
        print(f"  Storage Options: {storage_str}")
        print("-" * 80)

def get_available_plans(data: List[Dict]) -> Dict[str, Set[str]]:
    """Get all available plan IDs and titles across all groups"""
    plan_options = defaultdict(set)
    
    for group in data:
        for phone in group['phones']:
            if 'models' in phone:
                for model in phone['models']:
                    for plan in model.get('plans', []):
                        plan_id = plan['id']
                        plan_title = plan['title']
                        plan_data = plan.get('data', 'N/A')
                        plan_options[plan_id].add(f"{plan_title} ({plan_data}GB)")
    
    return dict(plan_options)

def print_available_plans(plans: Dict[str, Set[str]]):
    """Print all available plans"""
    print("\nAvailable Plans:")
    print("=" * 80)
    for plan_id, titles in plans.items():
        print(f"Plan ID: {plan_id}")
        for title in titles:
            print(f"  {title}")
        print("-" * 80)

def main():
    parser = argparse.ArgumentParser(description='Compare phone prices across different plans and groups')
    parser.add_argument('--list', action='store_true', 
                      help='List all available phones and storage options')
    parser.add_argument('--list-plans', action='store_true',
                      help='List all available plans')
    parser.add_argument('--phone-slug', help='Phone slug (e.g., "apple-iphone-16-pro")')
    parser.add_argument('--storage-size', type=int, help='Storage size in GB (e.g., 128)')
    parser.add_argument('--plan-id', help='Filter by specific plan ID')
    parser.add_argument('--sort', choices=['upfront', 'financing'], default='upfront',
                      help='Sort results by price type (default: upfront)')
    parser.add_argument('--upfront-name', default='Bring-It-Back',
                      help='Display name for upfront pricing (default: Bring-It-Back)')
    
    args = parser.parse_args()
    
    try:
        # Load the data
        data = load_data()
        
        # Handle --list-plans flag
        if args.list_plans:
            plans = get_available_plans(data)
            print_available_plans(plans)
            return
            
        # Get available phones
        available_phones = get_available_phones(data)
        
        if args.list:
            print_available_phones(available_phones)
            return
            
        if not args.phone_slug or not args.storage_size:
            print("Please provide both --phone-slug and --storage-size arguments")
            print("\nExample usage:")
            print("python query_phones.py --phone-slug apple-iphone-15-pro --storage-size 128")
            print("\nOr list available options:")
            print("python query_phones.py --list")
            print("python query_phones.py --list-plans")
            return
            
        # Find the phone with specific storage
        results = find_phone_by_slug_and_storage(data, args.phone_slug, args.storage_size)
        
        if not results:
            print(f"No groups found with phone: {args.phone_slug} and storage: {args.storage_size}GB")
            # Show similar matches to help user
            similar_phones = [p for p in available_phones if args.phone_slug.lower() in p[0].lower()]
            if similar_phones:
                print("\nDid you mean one of these?")
                print_available_phones(similar_phones)
            return
            
        # Get phone name for display
        phone_name = f"{results[0]['phones'][0]['brand']} {results[0]['phones'][0]['name']} ({args.storage_size}GB)"
        print(f"Found {phone_name} in {len(results)} groups")
        
        if args.plan_id:
            print(f"Filtering for plan ID: {args.plan_id}")
        
        if args.sort:
            print(f"Sorting by {args.sort} price")
        
        # Compare prices across groups
        plan_comparison = compare_plan_prices(results, args.sort, args.plan_id)
        
        if not plan_comparison:
            print(f"No matching plans found{' for plan ID: ' + args.plan_id if args.plan_id else ''}")
            return
            
        print_price_comparison(plan_comparison, phone_name, args.upfront_name)
        
        # Save filtered results
        output_file = f'data/{args.phone_slug}_{args.storage_size}gb_filtered.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nFull results saved to: {output_file}")
        
    except FileNotFoundError:
        print("Error: Could not find the data file. Make sure 'final_data.json' exists in the data directory.")
    except json.JSONDecodeError:
        print("Error: Invalid JSON data in the file.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()