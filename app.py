#!/usr/bin/env python3
"""
WooCommerce Product Data Extractor - Web Interface
"""
import os
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from werkzeug.utils import secure_filename
from wootomator import process_image_urls, WooCommerceCSVExporter
from dotenv import load_dotenv
import logging
from datetime import datetime
import copy
import json

# Load environment variables
load_dotenv(override=True)

# Debug: Print all environment variables
print("DEBUG: All environment variables:")
for key, value in os.environ.items():
    print(f"{key} = {value}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('wootomator_web.log')
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Add context processor to make current datetime available in all templates
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'txt'}

def allowed_file(filename):
    if not filename:
        return False
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    logger.info("Processing request to /process endpoint")
    logger.debug(f"Request form data: {request.form}")
    logger.debug(f"Request files: {request.files}")
    
    if 'urls' not in request.form and 'file' not in request.files:
        error_msg = 'No URLs or file provided in request'
        logger.error(error_msg)
        return jsonify({
            'success': False,
            'error': error_msg
        }), 400
    
    # Get URLs from form or file
    urls = []
    
    # Check if URLs were provided directly
    if request.form.get('urls'):
        logger.info("Found URLs in form data")
        urls = [url.strip() for url in request.form['urls'].split('\n') if url.strip()]
    
    # Check if a file was uploaded
    if 'file' in request.files:
        file = request.files['file']
        logger.info(f"Processing uploaded file: {file.filename}")
        
        if file.filename != '':
            if file and allowed_file(file.filename):
                # Ensure file.filename is not None before passing to secure_filename
                filename = secure_filename(file.filename) if file.filename else 'uploaded_file.txt'
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                logger.debug(f"Saving uploaded file to: {filepath}")
                
                try:
                    file.save(filepath)
                    logger.info(f"Successfully saved file to {filepath}")
                    
                    # Read URLs from file
                    with open(filepath, 'r') as f:
                        file_urls = [line.strip() for line in f if line.strip()]
                    urls.extend(file_urls)
                    logger.info(f"Read {len(file_urls)} URLs from file")
                    
                except Exception as e:
                    error_msg = f'Error processing file: {str(e)}'
                    logger.error(error_msg)
                    return jsonify({
                        'success': False,
                        'error': error_msg
                    }), 400
    
    if not urls:
        error_msg = 'No valid URLs found in the request'
        logger.error(error_msg)
        return jsonify({
            'success': False,
            'error': error_msg
        }), 400
    
    # Get API key from environment
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        error_msg = 'Gemini API key not configured. Please set GEMINI_API_KEY in your environment variables.'
        logger.error(error_msg)
        return jsonify({
            'success': False,
            'error': error_msg
        }), 500
    
    try:
        # Process the image URLs with Gemini API
        logger.info(f"Starting to process {len(urls)} URLs with Gemini API")
        
        # Process all products (without size variations)
        products = process_image_urls(urls, api_key, [])
        
        if not products:
            error_msg = 'No products were generated. Please check the image URLs and try again.'
            logger.error(error_msg)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        # Prepare response with product data
        response_data = {
            'success': True,
            'products': [{
                'name': p.name,
                'sku': p.sku,
                'regular_price': p.regular_price,
                'sale_price': p.sale_price,
                'short_description': p.short_description,
                'image': p.images.split(',')[0] if hasattr(p, 'images') and p.images else ''
            } for p in products if hasattr(p, 'name')]
        }
        
        logger.info(f"Successfully processed {len(products)} products")
        return jsonify(response_data)
            
    except Exception as e:
        error_msg = f"Error processing request: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return jsonify({
            'success': False,
            'error': error_msg
        }), 500

@app.route('/generate_csv', methods=['POST'])
def generate_csv():
    logger.info("Processing request to /generate_csv endpoint")
    
    if not request.is_json:
        return jsonify({
            'success': False,
            'error': 'Request must be JSON'
        }), 400
    
    data = request.get_json()
    
    # Validate required fields
    if 'products' not in data or not isinstance(data['products'], list):
        return jsonify({
            'success': False,
            'error': 'Products data is required and must be an array'
        }), 400
    
    if 'sizes' not in data or not isinstance(data['sizes'], list) or not data['sizes']:
        return jsonify({
            'success': False,
            'error': 'At least one size must be selected'
        }), 400
    
    try:
        # Create product variations for each size
        products_with_variations = []
        
        for product_data in data['products']:
            if not isinstance(product_data, dict) or 'sku' not in product_data:
                continue
                
            # Create a base product (parent)
            base_product = type('Product', (), {
                'name': product_data.get('name', 'Product'),
                'sku': product_data.get('sku', ''),
                'regular_price': product_data.get('regular_price', '0.00'),
                'sale_price': product_data.get('sale_price', ''),
                'short_description': product_data.get('short_description', ''),
                'images': product_data.get('image', ''),
                'type': 'variable',
                'attribute_1_name': 'Size',
                'attribute_1_values': '|'.join(data['sizes']),
                'attribute_1_visible': '1',
                'attribute_1_global': '0'
            })
            
            # Add the parent product
            products_with_variations.append(base_product)
            
            # Create variations for each size
            for size in data['sizes']:
                variation = type('Product', (), {
                    'name': f"{product_data.get('name', 'Product')} - {size}",
                    'sku': f"{product_data.get('sku', '')}-{size}",
                    'regular_price': product_data.get('regular_price', '0.00'),
                    'sale_price': product_data.get('sale_price', ''),
                    'short_description': product_data.get('short_description', ''),
                    'images': product_data.get('image', ''),
                    'type': 'variation',
                    'parent_sku': product_data.get('sku', ''),
                    'attribute_1_name': 'Size',
                    'attribute_1_values': size,
                    'attribute_1_visible': '1',
                    'attribute_1_global': '0'
                })
                products_with_variations.append(variation)
        
        if not products_with_variations:
            return jsonify({
                'success': False,
                'error': 'No valid products to export'
            }), 400
        
        # Generate a unique filename for the CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"woocommerce_products_{timestamp}.csv"
        csv_path = os.path.join(app.config['UPLOAD_FOLDER'], csv_filename)
        
        # Save products to CSV
        WooCommerceCSVExporter.save_to_csv(products_with_variations, csv_path)
        logger.info(f"Saved {len(products_with_variations)} products to {csv_path}")
        
        return jsonify({
            'success': True,
            'download_url': f'/download/{csv_filename}'
        })
        
    except Exception as e:
        error_msg = f"Error generating CSV: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return jsonify({
            'success': False,
            'error': error_msg
        }), 500

@app.route('/download/<filename>')
def download(filename):
    try:
        # Ensure the filename is safe and doesn't contain any directory traversal
        safe_filename = os.path.basename(filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        logger.info(f"Attempting to download file: {filepath}")
        
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return "File not found", 404
            
        logger.info(f"Sending file: {filepath}")
        
        # Generate a friendly download filename with timestamp
        download_filename = f'woocommerce_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        # Send the file with proper MIME type and headers
        response = send_file(
            filepath,
            as_attachment=True,
            download_name=download_filename,
            mimetype='text/csv'
        )
        
        # Set additional headers to ensure proper file download
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        logger.info(f"File sent successfully: {filepath}")
        return response
    except Exception as e:
        logger.error(f"Error in download route: {str(e)}", exc_info=True)
        return f"Error downloading file: {str(e)}", 500

if __name__ == '__main__':
    # Use port 5002 to avoid conflicts with other services
    app.run(host='0.0.0.0', port=5002, debug=True)
