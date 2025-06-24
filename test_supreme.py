#!/usr/bin/env python3
import os
import sys
from wootomator import GeminiAPI, WooCommerceProduct, WooCommerceCSVExporter

def test_supreme_image(image_url):
    # Get API key from environment
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set")
        sys.exit(1)
    
    # Initialize Gemini API
    gemini = GeminiAPI(api_key)
    
    print(f"Testing image URL: {image_url}")
    print("Analyzing image...")
    
    try:
        # Analyze the image
        product_data = gemini.analyze_image(image_url)
        
        # Print the raw response
        print("\n=== Raw Product Data ===")
        for key, value in product_data.items():
            print(f"{key}: {value}")
        
        # Create a WooCommerce product
        product = WooCommerceProduct()
        product.id = 'test-123'
        product.sku = 'TEST-123'
        product.name = product_data.get('product_name', 'Unknown Product')
        
        # Set prices
        original_price = float(product_data.get('original_price', 0))
        product.regular_price = f'{original_price:.2f}'
        product.sale_price = f'{WooCommerceCSVExporter.calculate_sale_price(original_price):.2f}'
        
        # Print the product info
        print("\n=== WooCommerce Product ===")
        print(f"Name: {product.name}")
        print(f"Original Price: ${original_price:.2f}")
        print(f"Sale Price: ${float(product.sale_price):.2f}")
        
        # Check if 'supreme' is in the product name or brand (case insensitive)
        if 'supreme' in product.name.lower() or (product_data.get('brand') and 'supreme' in product_data['brand'].lower()):
            print("\n✅ Success: Correctly identified Supreme product!")
        else:
            print("\n❌ Failed: Did not identify this as a Supreme product")
        
    except Exception as e:
        print(f"\n❌ Error analyzing image: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Test with the provided Supreme image URL
    test_url = "https://ablohs.com/wp-content/uploads/2025/06/fdg.png"
    test_supreme_image(test_url)
