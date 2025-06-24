#!/usr/bin/env python3
"""
Test script for product generation with the WooCommerce Product Generator.
"""
import os
import sys
import time
import json
from datetime import datetime
from wootomator import process_image_urls

def main():
    # Get API key from environment
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set")
        sys.exit(1)
    
    # Test with multiple image URLs
    test_urls = [
        "https://ablohs.com/wp-content/uploads/2025/06/hgfkhfg.png",
        "https://ablohs.com/wp-content/uploads/2025/06/77.png",
        "https://ablohs.com/wp-content/uploads/2025/06/ssee.png",
        "https://ablohs.com/wp-content/uploads/2025/06/sshh.png"
    ]
    
    sizes = ['S', 'M', 'L', 'XL']
    
    print(f"Testing with {len(test_urls)} image URLs and {len(sizes)} sizes each...")
    print(f"Expected products: {len(test_urls) * (len(sizes) + 1)} (base products + variations)")
    
    # Process the URLs with timing
    try:
        start_time = time.time()
        print(f"\nStarting processing at {datetime.now().strftime('%H:%M:%S')}")
        
        # Process with default concurrency (4 workers)
        products = process_image_urls(test_urls, api_key, sizes)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\nProcessing completed in {duration:.2f} seconds")
        print(f"Successfully generated {len(products)} products/variations")
        print(f"Average time per product: {duration/len(test_urls):.2f}s")
        
        # Print summary of products
        base_products = [p for p in products if p.type != 'variation']
        variations = [p for p in products if p.type == 'variation']
        
        print(f"\nSummary:")
        print(f"- Base products: {len(base_products)}")
        print(f"- Variations: {len(variations)}")
        
        # Print details of first product and its variations as an example
        if base_products:
            print("\n--- Example Product ---")
            p = base_products[0]
            print(f"Name: {p.name}")
            print(f"SKU: {p.sku}")
            print(f"Price: ${p.regular_price} (sale: ${p.sale_price})")
            print(f"Description: {p.short_description[:150]}..." if p.short_description else "No description")
            
            # Show variations for this product
            product_variations = [v for v in variations if v.parent == p.sku]
            if product_variations:
                print(f"\nVariations (SKUs):")
                for v in product_variations:
                    print(f"- {v.name}: {v.sku} (${v.sale_price})")
        
    except Exception as e:
        print(f"Error during product generation: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
