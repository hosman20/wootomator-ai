#!/usr/bin/env python3
"""
WooCommerce Product Data Extractor

This script processes product images using Google Gemini API and generates
WooCommerce-compatible CSV files for import.
"""
import os
import csv
import json
import logging
import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from PIL import Image
import io
import google.generativeai as genai
from google.generativeai.client import configure
from google.generativeai.generative_models import GenerativeModel
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('wootomator.log')
    ]
)
logger = logging.getLogger(__name__)

def get_env_float(key, default):
    """Safely get a float value from environment variables."""
    value = os.getenv(key, '').strip()
    if not value:
        return default
    try:
        # Remove any trailing comments and whitespace
        value = value.split('#')[0].strip()
        return float(value)
    except (ValueError, TypeError):
        print(f"Warning: Invalid value for {key}, using default: {default}")
        return default

def get_env_str(key, default):
    """Safely get a string value from environment variables."""
    value = os.getenv(key, default)
    if value is not None:
        value = value.strip()
        # Remove any trailing comments if present
        if '#' in value:
            value = value.split('#')[0].strip()
    return value or default

# Load environment variables - force reload
load_dotenv(override=True)

# Debug: Print environment variables
print("DEBUG: Current working directory:", os.getcwd())
print("DEBUG: Environment variables:")
for key in ['GEMINI_API_KEY', 'DISCOUNT_PERCENTAGE', 'MINIMUM_SALE_PRICE', 'OUTPUT_FILENAME']:
    print(f"  {key} = {os.getenv(key)}")

# Configuration with safe defaults
GEMINI_API_KEY = get_env_str('GEMINI_API_KEY', '')
DISCOUNT_PERCENTAGE = get_env_float('DISCOUNT_PERCENTAGE', 0.80)
MINIMUM_SALE_PRICE = get_env_float('MINIMUM_SALE_PRICE', 120.00)
OUTPUT_FILENAME = get_env_str('OUTPUT_FILENAME', 'woocommerce_products_export.csv')

@dataclass
class WooCommerceProduct:
    """Represents a WooCommerce product with all required fields."""
    # Core product data
    id: str = ''  # Will be auto-generated if empty
    type: str = 'simple'  # simple, variable, grouped, external
    sku: str = ''  # Stock Keeping Unit
    gtin_upc_ean_isbn: str = ''  # GTIN, UPC, EAN, or ISBN
    name: str = ''
    published: str = '1'  # 1 = published, 0 = draft
    is_featured: str = '0'  # 1 = yes, 0 = no
    visibility: str = 'visible'  # visible, catalog, search, hidden
    short_description: str = ''
    description: str = ''
    date_sale_price_starts: str = ''  # YYYY-MM-DD
    date_sale_price_ends: str = ''    # YYYY-MM-DD
    tax_status: str = 'taxable'  # taxable, shipping, none
    tax_class: str = ''  # standard, reduced-rate, zero-rate
    in_stock: str = '1'  # 1 = in stock, 0 = out of stock
    stock: str = '100'  # Stock quantity
    low_stock_amount: str = '2'  # Threshold for low stock alerts
    backorders_allowed: str = '0'  # 0 = no, 1 = notify, 2 = yes
    sold_individually: str = '0'  # 1 = yes, 0 = no
    weight_lbs: str = '1'  # Product weight in pounds
    length_in: str = '10'  # Product length in inches
    width_in: str = '10'   # Product width in inches
    height_in: str = '5'   # Product height in inches
    allow_customer_reviews: str = '1'  # 1 = yes, 0 = no
    purchase_note: str = ''  # Optional note to send to customer after purchase
    sale_price: str = ''  # Current sale price
    regular_price: str = ''  # Regular price
    categories: str = ''  # Comma-separated category names
    tags: str = ''  # Comma-separated tag names
    shipping_class: str = ''  # Shipping class slug
    images: str = ''  # Comma-separated image URLs
    download_limit: str = ''  # Max downloads for downloadable products
    download_expiry_days: str = ''  # Number of days download link is valid
    parent: str = ''  # Parent product ID for variations
    grouped_products: str = ''  # Comma-separated product IDs
    upsells: str = ''  # Comma-separated product IDs
    cross_sells: str = ''  # Comma-separated product IDs
    external_url: str = ''  # For external/affiliate products
    button_text: str = ''  # Text for external product button
    position: str = '0'  # Menu order
    brands: str = ''  # Comma-separated brand names
    attribute_1_name: str = 'Brand'  # Attribute name
    attribute_1_values: str = ''  # Attribute value(s)
    attribute_1_visible: str = '1'  # 1 = visible, 0 = not visible
    attribute_1_global: str = '0'  # 0 = not global (local to product), 1 = global
    
    def to_csv_dict(self) -> dict:
        """Convert to dictionary with proper CSV headers."""
        return {
            'ID': self.id,
            'Type': self.type,
            'SKU': self.sku,
            'GTIN, UPC, EAN, or ISBN': self.gtin_upc_ean_isbn,
            'Name': self.name,
            'Published': self.published,
            'Is featured?': self.is_featured,
            'Visibility in catalog': self.visibility,
            'Short description': self.short_description,
            'Description': self.description,
            'Date sale price starts': self.date_sale_price_starts,
            'Date sale price ends': self.date_sale_price_ends,
            'Tax status': self.tax_status,
            'Tax class': self.tax_class,
            'In stock?': self.in_stock,
            'Stock': self.stock,
            'Low stock amount': self.low_stock_amount,
            'Backorders allowed?': self.backorders_allowed,
            'Sold individually?': self.sold_individually,
            'Weight (lbs)': self.weight_lbs,
            'Length (in)': self.length_in,
            'Width (in)': self.width_in,
            'Height (in)': self.height_in,
            'Allow customer reviews?': self.allow_customer_reviews,
            'Purchase note': self.purchase_note,
            'Sale price': self.sale_price,
            'Regular price': self.regular_price,
            'Categories': self.categories,
            'Tags': self.tags,
            'Shipping class': self.shipping_class,
            'Images': self.images,
            'Download limit': self.download_limit,
            'Download expiry days': self.download_expiry_days,
            'Parent': self.parent,
            'Grouped products': self.grouped_products,
            'Upsells': self.upsells,
            'Cross-sells': self.cross_sells,
            'External URL': self.external_url,
            'Button text': self.button_text,
            'Position': self.position,
            'Brands': self.brands,
            'Attribute 1 name': self.attribute_1_name,
            'Attribute 1 value(s)': self.attribute_1_values,
            'Attribute 1 visible': self.attribute_1_visible,
            'Attribute 1 global': self.attribute_1_global
        }

class GeminiAPI:
    """Handles communication with Google Gemini API."""
    
    def __init__(self, api_key: str):
        """Initialize the Gemini API client."""
        configure(api_key=api_key)
        self.model = GenerativeModel('gemini-1.5-flash')
    
    def analyze_image(self, image_url: str) -> Dict[str, Any]:
        """Analyze product image and extract information using Gemini.
        
        Args:
            image_url: URL of the product image to analyze
            
        Returns:
            Dict containing product information with at least 'original_price' and 'product_name'
        """
        logger.info(f"Analyzing image: {image_url}")
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Download the image with timeout
                response = requests.get(image_url, timeout=10)
                response.raise_for_status()
                
                # Convert image to bytes and verify it
                image_bytes = io.BytesIO(response.content)
                img = Image.open(image_bytes)
                
                # Ensure image is in RGB mode
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Save the image to a temporary file
                temp_img_path = f"temp_{int(time.time())}.jpg"
                img.save(temp_img_path, 'JPEG')
                
                # Read the image file as bytes
                with open(temp_img_path, 'rb') as img_file:
                    image_data = img_file.read()
                
                # Clean up temporary file
                try:
                    os.remove(temp_img_path)
                except Exception as e:
                    logger.warning(f"Could not remove temp file {temp_img_path}: {str(e)}")
            
                # Prepare the prompt with clear instructions for product analysis
                prompt = """CRITICAL INSTRUCTION: You are an expert in streetwear and luxury fashion pricing. Your task is to find the HIGHEST POSSIBLE PRICE this item could sell for.

PRICING RESEARCH HIERARCHY (in order of preference):
1. BRAND'S OFFICIAL WEBSITE: Check the brand's official online store for current retail price
   - Example: supreme.com for Supreme items
   - Look for any official pricing information
   - Note if the item is currently in stock or sold out

2. AUTHORIZED RETAILERS: Check official brand-authorized retailers
   - Example: SSENSE, END Clothing, DSM for high-end streetwear
   - Look for any current sales or promotions

3. RESALE MARKETPLACES (if official sources unavailable or sold out):
   - StockX (most reliable for recent sale data)
   - GOAT (especially for rare/limited items)
   - Grailed (for streetwear and luxury)
   - Stadium Goods (for authenticated items)
   - eBay (filter for sold listings only)
   - Vestiaire Collective (for luxury items)

4. HISTORICAL DATA:
   - Check historical sale prices for the same item
   - Note any price trends (increasing/decreasing)
   - Consider seasonality and current market demand

RULES FOR PRICING:
1. ALWAYS start by checking the brand's official website first
2. If the item is SOLD OUT on the brand's site, check authorized retailers
3. Only use resale market data if official sources are unavailable or the item is sold out
4. For resale prices, ALWAYS use the HIGHEST recent sale price
5. For Supreme and other hype brands, the resale price is typically 2-10x retail depending on rarity
6. If the item is rare, limited edition, or from a sought-after collection, use the HIGHEST comparable sale
7. Always document your price sources in the description

{
    "product_name": "Exact product name with details (e.g., 'Supreme Box Logo Tee SS20 Black')",
    "original_price": 0.0,  # MUST be the HIGHEST POSSIBLE price found
    "categories": ["Main Category", "Subcategory"],
    "brand": "Brand name if visible (e.g., 'Supreme')",
    "short_description": "Brief product description highlighting value factors",
    "detailed_description": [
        "PRICE SOURCES CHECKED:",
        "1. Brand Website: [Status - Available/Sold Out/Not Found] | Price: $",
        "2. Authorized Retailers: [List any checked] | Best Price: $",
        "3. Resale Markets: [StockX/GOAT/Grailed] | Recent High: $",
        "4. Market Analysis: [Summary of price factors]",
        "",
        "PRODUCT DETAILS:",
        "• Key feature 1 that affects value",
        "• Key feature 2 that affects value",
        "• Condition notes",
        "• Why this commands a premium price"
    ]
}

EXAMPLE 1 - Supreme Box Logo (Official + Resale):
{
    "product_name": "Supreme Box Logo Hoodie FW20 Black",
    "original_price": 1299.00,  # Based on highest verified sale
    "categories": ["Clothing", "Hoodies"],
    "brand": "Supreme",
    "short_description": "Highly sought-after Supreme Box Logo Hoodie from Fall/Winter 2020 collection in black.",
    "detailed_description": [
        "PRICE SOURCES CHECKED:",
        "1. Brand Website: [Status - Sold Out] | Original Retail: $168",
        "2. Authorized Retailers: [SSENSE, DSM, END] | All Sold Out",
        "3. Resale Markets: [StockX] 30d Avg: $1,100 | Recent High: $1,450",
        "4. Market Analysis: [High demand, limited restocks, black colorway premium]",
        "",
        "PRODUCT DETAILS:",
        "• Original Retail: $168 (sold out immediately)",
        "• Current Market Value: $1,100-$1,450",
        "• Black colorway commands 20% premium over others",
        "• Features iconic box logo on chest",
        "• Heavyweight cotton blend with premium construction"
    ]
}

EXAMPLE 2 - Supreme x Louis Vuitton (Rare Collaboration):
{
    "product_name": "Supreme x Louis Vuitton Box Logo Tee (2017)",
    "original_price": 4200.00,  # Premium for DS condition
    "categories": ["Clothing", "T-Shirts", "Collaborations"],
    "brand": "Supreme x Louis Vuitton",
    "short_description": "Ultra-rare DS Supreme x Louis Vuitton Box Logo Tee from the historic 2017 collaboration.",
    "detailed_description": [
        "PRICE SOURCES CHECKED:",
        "1. Brand Website: [Status - Never Available Online] | Original Retail: $310",
        "2. Authorized Retailers: [Louis Vuitton Flagships Only] | Sold Out Worldwide",
        "3. Resale Markets: [Grailed/GOAT] Last DS Sale: $4,200",
        "4. Market Analysis: [Extremely limited, DS condition commands 2x premium]",
        "",
        "PRODUCT DETAILS:",
        "• Original Retail: $310 (in-store only, extremely limited)",
        "• Current Market Value: $3,500-$4,200 for DS",
        "• Historic collaboration with Louis Vuitton",
        "• Features co-branded box logo and LV monogram",
        "• Deadstock condition with original tags"
    ]
}

IMPORTANT PRICING RULES:
1. Always document ALL sources checked in the detailed description
2. For brand websites: Note if the item is in stock, sold out, or not found
3. For resale markets: Include the platform and highest recent sale price
4. If an item is sold out at retail, use the highest resale price you can justify
5. For rare/limited items, emphasize scarcity and historical appreciation
6. Never be conservative - we want the highest justifiable price the market will bear

FINAL CHECK: Before submitting, verify you've:
- Checked the brand's official website
- Verified stock status across major retailers
- Researched recent resale prices on multiple platforms
- Documented all sources in the detailed description
- Justified the price with specific market data"""
                
                # Generate content with the prompt and image data
                response = self.model.generate_content([
                    prompt,
                    {"mime_type": "image/jpeg", "data": image_data}
                ])
                
                # Get the text content from the response
                response_text = response.text
                
                # Log the raw response for debugging
                logger.debug(f"Raw Gemini API response: {response_text}")
                
                # Clean the response text to handle markdown code blocks
                if '```json' in response_text and '```' in response_text[response_text.find('```json') + 6:]:
                    # Extract JSON from markdown code block
                    json_start = response_text.find('{', response_text.find('```json'))
                    json_end = response_text.rfind('}') + 1
                    response_text = response_text[json_start:json_end]
                
                # Parse the response
                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {response_text}")
                    raise ValueError(f"Invalid JSON response: {str(e)}")
                
                # Validate the response contains required fields
                if not isinstance(result, dict):
                    raise ValueError(f"Response is not a valid JSON object: {result}")
                
                # Ensure we have a product name
                if not result.get('product_name'):
                    # Try to extract product name from response text if not in JSON
                    if 'product_name' in response_text:
                        name_start = response_text.find('"product_name":') + 15
                        name_end = response_text.find('"', name_start + 1)
                        if name_start > 14 and name_end > name_start:
                            result['product_name'] = response_text[name_start:name_end].strip('\"')
                
                # If we still don't have a product name, try to extract it from the URL
                if not result.get('product_name'):
                    filename = image_url.split('/')[-1].split('?')[0]
                    result['product_name'] = f"Product {filename}"
                
                # Ensure we have a valid price
                if 'original_price' not in result or not isinstance(result['original_price'], (int, float)) or result['original_price'] <= 0:
                    # Try to find a price in the response text
                    import re
                    price_matches = re.findall(r'\$?\s*(\d+(\.\d{1,2})?)', response_text)
                    if price_matches:
                        try:
                            result['original_price'] = float(price_matches[0][0])
                            logger.info(f"Extracted price from response text: {result['original_price']}")
                        except (ValueError, IndexError):
                            result['original_price'] = 199.99  # Default price
                    else:
                        result['original_price'] = 199.99  # Default price
                
                # Try to identify brand from product name if not set
                if not result.get('brand') or result['brand'].lower() == 'unknown':
                    if 'supreme' in result['product_name'].lower():
                        result['brand'] = 'Supreme'
                
                logger.info(f"Successfully analyzed image {image_url} (attempt {attempt + 1})")
                return result
                
            except Exception as e:
                if attempt == max_retries - 1:  # Last attempt
                    logger.error(f"Failed to analyze image {image_url} after {max_retries} attempts: {str(e)}")
                    # Return a default response with estimated price based on product type
                    return {
                        'product_name': f"Product from {image_url.split('/')[-1].split('?')[0]}",
                        'original_price': 199.99,  # Default price
                        'categories': ['Uncategorized'],
                        'brand': 'Unknown',
                        'short_description': 'Product details not available',
                        'detailed_description': ['No description available']
                    }
                logger.warning(f"Attempt {attempt + 1} failed for {image_url}, retrying...")
                time.sleep(1)  # Add a small delay between retries
        
        # If we get here, all retries failed
        return {
            'product_name': f"Product from {image_url.split('/')[-1].split('?')[0]}",
            'original_price': 199.99,
            'categories': ['Uncategorized'],
            'brand': 'Unknown',
            'short_description': 'Failed to analyze product image',
            'detailed_description': ['Error processing product image']
        }

class WooCommerceCSVExporter:
    """Handles CSV export in WooCommerce import format."""
    
    @staticmethod
    def calculate_sale_price(original_price: float) -> float:
        """Calculate sale price with discount and minimum price enforcement."""
        sale_price = original_price * (1 - DISCOUNT_PERCENTAGE)
        return max(sale_price, MINIMUM_SALE_PRICE)
    
    @staticmethod
    def product_to_dict(product: WooCommerceProduct) -> Dict[str, str]:
        """Convert WooCommerceProduct to dictionary for CSV export."""
        return product.to_csv_dict()
    
    @staticmethod
    def save_to_csv(products: List[WooCommerceProduct], filename: str) -> bool:
        """Save products to a CSV file in WooCommerce import format.
        
        Args:
            products: List of WooCommerceProduct objects to save
            filename: Output CSV filename
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not products:
            logger.warning("No products to save to CSV")
            return False
            
        try:
            # Ensure the output directory exists
            output_dir = os.path.dirname(os.path.abspath(filename))
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                
            # Get field names from the first product
            fieldnames = list(products[0].to_csv_dict().keys())
            
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for product in products:
                    writer.writerow(product.to_csv_dict())
            
            # Verify the file was created and has content
            if os.path.exists(filename):
                file_size = os.path.getsize(filename)
                if file_size > 0:
                    logger.info(f"Successfully saved {len(products)} products to {filename} (size: {file_size} bytes)")
                    return True
                else:
                    logger.error(f"Failed to write to {filename}: file is empty")
                    return False
            else:
                logger.error(f"Failed to create file: {filename}")
                return False
                
        except Exception as e:
            logger.error(f"Error saving products to {filename}: {str(e)}")
            return False
        
def _process_single_image(url: str, api_key: str, sizes: List[str]) -> List[WooCommerceProduct]:
    """Process a single image URL and return a list of WooCommerce products."""
    gemini = GeminiAPI(api_key)
    products = []
    
    try:
        logger.info(f"Processing image: {url}")
        
        # Analyze the image
        product_data = gemini.analyze_image(url)
        
        # Create base product
        base_product = WooCommerceProduct()
        product_name = product_data.get('product_name', 'Unnamed Product')
        base_product.name = product_name
        base_sku = product_data.get('sku', f'PROD-{int(time.time())}')
        base_product.sku = base_sku
        
        # Handle price calculation
        try:
            original_price = float(product_data.get('original_price', 0))
            sale_price = max(
                original_price * (1 - DISCOUNT_PERCENTAGE),
                MINIMUM_SALE_PRICE
            )
            base_product.regular_price = f"{original_price:.2f}"
            base_product.sale_price = f"{sale_price:.2f}"
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid price data: {e}")
            base_product.regular_price = "0.00"
            base_product.sale_price = str(MINIMUM_SALE_PRICE)
        
        # Set product details
        base_product.short_description = product_data.get('short_description', '')
        base_product.description = product_data.get('description', '')
        base_product.images = url
        
        # Set brand as an attribute
        if 'brand' in product_data:
            base_product.attribute_1_name = 'Brand'
            base_product.attribute_1_values = product_data['brand']
            base_product.attribute_1_visible = '1'
            base_product.attribute_1_global = '0'  # Local to this product
        
        if sizes:
            # Create variable product
            base_product.type = 'variable'
            base_product.attribute_1_name = 'Size'
            base_product.attribute_1_values = ','.join(sizes)
            base_product.attribute_1_visible = '1'
            base_product.attribute_1_global = '1'  # Global attribute
            
            # Add the base product
            products.append(base_product)
            
            # Create variations for each size
            for size in sizes:
                variation = WooCommerceProduct()
                variation.type = 'variation'
                variation.parent = base_sku
                variation.name = f"{product_name} - {size}"
                variation.regular_price = base_product.regular_price
                variation.sale_price = base_product.sale_price
                variation.sku = f"{base_sku}-{size}"
                variation.images = url
                variation.attribute_1_name = 'Size'
                variation.attribute_1_values = size
                variation.attribute_1_visible = '1'
                variation.attribute_1_global = '0'  # Local to this product
                variation.in_stock = '1'
                variation.stock = '10'  # Default stock quantity
                products.append(variation)
        else:
            # Simple product
            products.append(base_product)
            
    except Exception as e:
        logger.error(f"Error processing image {url}: {str(e)}", exc_info=True)
    
    return products

def process_image_urls(image_urls: List[str], api_key: str, sizes: Optional[List[str]] = None, max_workers: int = 4) -> List[WooCommerceProduct]:
    """Process a list of image URLs in parallel and return WooCommerce products.
    
    Args:
        image_urls: List of image URLs to process
        api_key: Gemini API key
        sizes: Optional list of sizes to generate variations for (e.g., ['S', 'M', 'L', 'XL'])
        max_workers: Maximum number of concurrent workers for parallel processing
        
    Returns:
        List of WooCommerceProduct objects with size variations if sizes are provided
    """
    if not image_urls:
        return []
    
    if sizes is None:
        sizes = []
    
    all_products = []
    
    # Process images in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create a future for each URL
        future_to_url = {
            executor.submit(_process_single_image, url, api_key, sizes): url 
            for url in image_urls
        }
        
        # Process results as they complete
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                products = future.result()
                if products:
                    all_products.extend(products)
            except Exception as e:
                logger.error(f"Error processing URL {url}: {str(e)}", exc_info=True)
    
    return all_products

def read_urls_from_file(filename: str) -> List[str]:
    """Read image URLs from a text file.
    
    Args:
        filename: Path to the file containing URLs (one per line)
        
    Returns:
        List of URLs as strings
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            # Read all non-empty lines and strip whitespace
            urls = [line.strip() for line in f if line.strip()]
            logger.info(f"Read {len(urls)} URLs from {filename}")
            return urls
    except FileNotFoundError:
        logger.error(f"File not found: {filename}")
        raise
    except Exception as e:
        logger.error(f"Error reading URLs from file {filename}: {str(e)}")
        raise

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Generate WooCommerce product CSV from image URLs')
    parser.add_argument('--urls', nargs='+', help='List of image URLs to process')
    parser.add_argument('--file', help='Text file containing one image URL per line')
    parser.add_argument('--output', help='Output CSV filename', default=OUTPUT_FILENAME)
    
    args = parser.parse_args()
    
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not found in environment variables. Please set it in the .env file.")
        return
    
    # Get URLs from command line or file
    image_urls = []
    if args.urls:
        image_urls = args.urls
    elif args.file:
        image_urls = read_urls_from_file(args.file)
    else:
        logger.error("Please provide either --urls or --file argument")
        return
    
    if not image_urls:
        logger.error("No image URLs provided")
        return
    
    logger.info(f"Starting processing of {len(image_urls)} images...")
    
    # Process images and generate products
    products = process_image_urls(image_urls, GEMINI_API_KEY)
    
    if not products:
        logger.error("No products were generated. Check the logs for errors.")
        return
    
    # Save to CSV
    WooCommerceCSVExporter.save_to_csv(products, args.output)

if __name__ == "__main__":
    main()
