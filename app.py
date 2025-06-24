#!/usr/bin/env python3
"""
WooCommerce Product Data Extractor - Web Interface
"""
import os
import sys
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from werkzeug.utils import secure_filename
from wootomator import process_image_urls, WooCommerceCSVExporter, WooCommerceProduct
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

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def ensure_upload_directory():
    """Ensure the upload directory exists and has the correct permissions."""
    try:
        # Create the directory if it doesn't exist
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        # Set permissions (read/write/execute for owner, read/execute for group/others)
        os.chmod(UPLOAD_FOLDER, 0o755)
        
        # Verify we can write to the directory
        test_file = os.path.join(UPLOAD_FOLDER, '.permission_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        
        logger.info(f"Upload directory verified and ready: {UPLOAD_FOLDER}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize upload directory {UPLOAD_FOLDER}: {str(e)}", exc_info=True)
        return False

# Ensure upload directory is ready
if not ensure_upload_directory():
    logger.critical("FATAL: Could not initialize upload directory. Check permissions and try again.")
    sys.exit(1)

# Add context processor to make current datetime available in all templates
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

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
    logger.debug(f"Request headers: {dict(request.headers)}")
    logger.debug(f"Request data length: {len(request.data) if request.data else 0}")
    
    if not request.is_json:
        error_msg = 'Request must be JSON'
        logger.error(error_msg)
        return jsonify({
            'success': False,
            'error': error_msg
        }), 400
    
    try:
        data = request.get_json()
        logger.debug(f"Received data: {json.dumps(data, indent=2) if data else 'No data'}")
        
        # Validate required fields
        if 'products' not in data or not isinstance(data['products'], list):
            error_msg = 'Products data is required and must be an array'
            logger.error(error_msg)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        if 'sizes' not in data or not isinstance(data['sizes'], list) or not data['sizes']:
            error_msg = 'At least one size must be selected'
            logger.error(error_msg)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        # Create product variations for each size
        products_with_variations = []
        logger.info(f"Processing {len(data['products'])} products with sizes: {', '.join(data['sizes'])}")
        
        for idx, product_data in enumerate(data['products'], 1):
            if not isinstance(product_data, dict) or 'sku' not in product_data:
                logger.warning(f"Skipping invalid product at index {idx}: {product_data}")
                continue
                
            logger.debug(f"Processing product {idx}: {product_data.get('name', 'Unnamed')} (SKU: {product_data.get('sku', 'N/A')})")
                
            # Create a base product (parent)
            base_product = WooCommerceProduct(
                name=product_data.get('name', 'Product'),
                sku=product_data.get('sku', ''),
                regular_price=product_data.get('regular_price', '0.00'),
                sale_price=product_data.get('sale_price', ''),
                short_description=product_data.get('short_description', ''),
                images=product_data.get('image', ''),
                type='variable',
                attribute_1_name='Size',
                attribute_1_values='|'.join(data['sizes']),
                attribute_1_visible='1',
                attribute_1_global='0'
            )
            
            # Add the parent product
            products_with_variations.append(base_product)
            
            # Create variations for each size
            for size in data['sizes']:
                variation = WooCommerceProduct(
                    name=f"{product_data.get('name', 'Product')} - {size}",
                    sku=f"{product_data.get('sku', '')}-{size}",
                    regular_price=product_data.get('regular_price', '0.00'),
                    sale_price=product_data.get('sale_price', ''),
                    short_description=product_data.get('short_description', ''),
                    images=product_data.get('image', ''),
                    type='variation',
                    parent=product_data.get('sku', ''),
                    attribute_1_name='Size',
                    attribute_1_values=size,
                    attribute_1_visible='1',
                    attribute_1_global='0'
                )
                products_with_variations.append(variation)
        
        if not products_with_variations:
            error_msg = 'No valid products to export'
            logger.error(error_msg)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        # Generate a unique filename for the CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"woocommerce_products_{timestamp}.csv"
        csv_path = os.path.join(app.config['UPLOAD_FOLDER'], csv_filename)
        
        logger.info(f"Saving {len(products_with_variations)} products to {csv_path}")
        
        # Ensure upload directory exists
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        # Save products to CSV
        WooCommerceCSVExporter.save_to_csv(products_with_variations, csv_path)
        
        if not os.path.exists(csv_path):
            error_msg = f"Failed to save CSV file at {csv_path}"
            logger.error(error_msg)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500
            
        logger.info(f"Successfully saved {len(products_with_variations)} products to {csv_path}")
        
        download_url = f'/download/{csv_filename}'
        logger.info(f"Generated download URL: {download_url}")
        
        return jsonify({
            'success': True,
            'download_url': download_url
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
        logger.info(f"Received download request for file: {filename}")
        
        # Ensure the filename is safe and doesn't contain any directory traversal
        safe_filename = os.path.basename(filename)
        if safe_filename != filename:
            logger.warning(f"Filename sanitized from '{filename}' to '{safe_filename}'")
            
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        logger.info(f"Resolved file path: {filepath}")
        
        # Verify file exists and is accessible
        if not os.path.exists(filepath):
            error_msg = f"File not found: {filepath}"
            logger.error(error_msg)
            return jsonify({
                'success': False,
                'error': 'File not found',
                'path': filepath
            }), 404
            
        # Verify it's a file (not a directory)
        if not os.path.isfile(filepath):
            error_msg = f"Path is not a file: {filepath}"
            logger.error(error_msg)
            return jsonify({
                'success': False,
                'error': 'Invalid file path',
                'path': filepath
            }), 400
            
        # Verify file size
        file_size = os.path.getsize(filepath)
        logger.info(f"File size: {file_size} bytes")
        
        if file_size == 0:
            error_msg = f"File is empty: {filepath}"
            logger.error(error_msg)
            return jsonify({
                'success': False,
                'error': 'File is empty',
                'path': filepath
            }), 400
            
        # Generate a friendly download filename with timestamp
        download_filename = f'woocommerce_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        logger.info(f"Serving file as: {download_filename}")
        
        # Prepare response with appropriate headers
        try:
            response = send_file(
                filepath,
                as_attachment=True,
                download_name=download_filename,
                mimetype='text/csv',
                etag=True,
                last_modified=datetime.now(),
                max_age=0  # Prevent caching
            )
            
            # Set additional headers to ensure proper file download
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            response.headers['Content-Length'] = file_size
            
            logger.info(f"Successfully prepared file for download: {filepath} ({file_size} bytes)")
            return response
            
        except Exception as e:
            error_msg = f"Error preparing file for download: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return jsonify({
                'success': False,
                'error': 'Error preparing file for download',
                'details': str(e)
            }), 500
            
    except Exception as e:
        error_msg = f"Error in download route: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(e) if app.debug else 'An error occurred while processing your request'
        }), 500

if __name__ == '__main__':
    import argparse
    
    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Run the WooCommerce Product Generator')
    parser.add_argument('--port', type=int, default=5003, help='Port to run the server on')
    args = parser.parse_args()
    
    # Use specified port or default to 5003
    port = int(os.environ.get('PORT', args.port))
    
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    logger.info(f"Starting server on port {port}")
    app.run(debug=True, host='0.0.0.0', port=port)
