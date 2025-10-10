"""Test script to verify DigitalOcean DNS connection"""
import requests
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# DigitalOcean credentials and configuration
API_TOKEN = os.getenv('DO_API_TOKEN')
DNS_ZONE = os.getenv('DO_DNS_ZONE')

print("Testing DigitalOcean DNS Connection...")
print(f"DNS Zone: {DNS_ZONE}")
print("-" * 50)

try:
    # Create headers
    print("\n1. Setting up API headers...")
    headers = {
        'Authorization': f"Bearer {API_TOKEN}",
        'Content-Type': 'application/json'
    }
    print("✓ Headers created successfully")
    
    # Try to list records
    print(f"\n2. Attempting to list records from zone: {DNS_ZONE}")
    response = requests.get(
        f"https://api.digitalocean.com/v2/domains/{DNS_ZONE}/records",
        headers=headers
    )
    
    if response.status_code == 200:
        records = response.json().get('domain_records', [])
        print(f"✓ Successfully retrieved {len(records)} records")
        
        # Display first few records
        print("\nFirst 5 records:")
        for i, record in enumerate(records[:5]):
            print(f"  - {record.get('name')} ({record.get('type')}) TTL: {record.get('ttl')} => {record.get('data')}")
        
        print("\n" + "=" * 50)
        print("✓ Connection test PASSED!")
        print("=" * 50)
    elif response.status_code == 401:
        print("\n" + "=" * 50)
        print("✗ Connection test FAILED!")
        print("=" * 50)
        print("\nAuthentication failed. Please check your API token.")
    elif response.status_code == 404:
        print("\n" + "=" * 50)
        print("✗ Connection test FAILED!")
        print("=" * 50)
        print(f"\nDNS zone '{DNS_ZONE}' not found in your DigitalOcean account.")
    else:
        print("\n" + "=" * 50)
        print("✗ Connection test FAILED!")
        print("=" * 50)
        print(f"\nError: HTTP {response.status_code}")
        print(f"Message: {response.json().get('message', 'Unknown error')}")
    
except requests.exceptions.RequestException as e:
    print("\n" + "=" * 50)
    print("✗ Connection test FAILED!")
    print("=" * 50)
    print(f"\nConnection error: {str(e)}")
    
except Exception as e:
    import traceback
    print("\n" + "=" * 50)
    print("✗ Connection test FAILED!")
    print("=" * 50)
    print(f"\nError: {str(e)}")
    print("\nFull traceback:")
    print(traceback.format_exc())
