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
        flash(error_msg, 'error')
        return redirect(url_for('index'))
    
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
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                logger.debug(f"Saving uploaded file to: {filepath}")
                
                try:
                    file.save(filepath)
                    logger.info(f"Successfully saved file to {filepath}")
                    
                    # Read URLs from file
                    with open(filepath, 'r') as f:
                        file_urls = [line.strip() for line in f if line.strip()]
                        logger.info(f"Read {len(file_urls)} URLs from file")
                        urls.extend(file_urls)
                    
                    # Clean up the uploaded file
                    os.remove(filepath)
                    logger.debug(f"Removed temporary file: {filepath}")
                    
                except Exception as e:
                    error_msg = f"Error processing uploaded file: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    return jsonify({
                        'success': False,
                        'error': error_msg
                    }), 400
    
    if not urls:
        error_msg = 'No valid URLs provided after processing form and file uploads'
        logger.error(error_msg)
        return jsonify({
            'success': False,
            'error': error_msg
        }), 400
    
    logger.info(f"Processing {len(urls)} image URLs")
    
    try:
        # Get API key from environment
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            error_msg = 'GEMINI_API_KEY environment variable is not set'
            logger.error(error_msg)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500
            
        logger.debug(f"Using API key: {api_key[:5]}...{api_key[-3:] if api_key else ''}")
        
        # Process the URLs
        logger.info("Starting to process image URLs with Gemini API")
        products = process_image_urls(urls, api_key)
        
        if not products:
            error_msg = 'No products were generated. Please check the image URLs and try again.'
            logger.error(error_msg)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        logger.info(f"Successfully processed {len(products)} products")
        
        # Generate a unique filename for the CSV
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f'woocommerce_export_{timestamp}.csv'
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        
        logger.info(f"Saving {len(products)} products to CSV: {output_path}")
        
        # Save to CSV
        csv_saved = WooCommerceCSVExporter.save_to_csv(products, output_path)
        
        if not csv_saved:
            error_msg = f'Failed to save products to CSV: {output_path}'
            logger.error(error_msg)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500
            
        logger.info(f"Successfully saved CSV to {output_path}")
        
        # Verify the file exists and has content
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            error_msg = f'CSV file was created but is empty: {output_path}'
            logger.error(error_msg)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500
        
        # Prepare product data for the web interface
        logger.debug("Preparing product data for web interface")
        web_products = []
        for p in products:
            web_products.append({
                'name': p.name,
                'regular_price': p.regular_price,
                'sale_price': p.sale_price,
                'short_description': p.short_description,
                'sku': p.sku,
                'image': p.images.split(',')[0] if p.images else ''  # Just show first image in the list
            })
        
        download_url = url_for('download', filename=output_filename, _external=True)
        logger.info(f"Generated download URL: {download_url}")
        
        # Return response with download URL and product data
        response_data = {
            'success': True,
            'download_url': download_url,
            'products': web_products,
            'csv_path': output_path
        }
        
        logger.info("Successfully completed request processing")
        return jsonify(response_data)
        
    except Exception as e:
        error_msg = f"Error processing request: {str(e)}"
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
