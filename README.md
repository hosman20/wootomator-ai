# Wootomator AI

A Flask web application that processes product images using Google Gemini AI to extract product information and generates WooCommerce-compatible CSV files for easy import.

## Features

- **Web Interface**: User-friendly web interface for easy interaction
- **Multiple Input Methods**:
  - Direct URL input
  - File upload for batch processing
- **AI-Powered Extraction**: Uses Google Gemini 2.5 Flash API for accurate product data extraction
- **Smart Pricing**:
  - Applies an 80% discount to original prices
  - Enforces a minimum sale price of $120
- **WooCommerce Ready**:
  - Generates properly formatted WooCommerce CSV import files
  - Includes all required WooCommerce fields
  - Clean, formatted product descriptions
- **Responsive Design**: Works on desktop and mobile devices

## Prerequisites

- Python 3.8+
- Google Gemini API key
- WooCommerce store (for importing the generated CSV)

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/hosman20/wootomator-ai.git
   cd wootomator-ai
   ```

2. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file and add your configuration:
   ```bash
   cp .env.example .env
   # Edit .env and add your API key and other settings
   ```

## Usage

### Basic Usage

Process a single image URL:
```bash
python wootomator.py --urls "https://example.com/product1.jpg"
```

Process multiple image URLs:
```bash
python wootomator.py --urls "https://example.com/product1.jpg" "https://example.com/product2.jpg"
```

Process URLs from a text file (one URL per line):
```bash
python wootomator.py --file urls.txt
```

Specify a custom output filename:
```bash
python wootomator.py --file urls.txt --output my_products.csv
```

### Output

The script will generate a CSV file (`woocommerce_products_export.csv` by default) that can be imported directly into WooCommerce using the built-in product importer.

## Configuration

Edit the `.env` file to customize:

- `GEMINI_API_KEY`: Your Google Gemini API key (required)
- `DISCOUNT_PERCENTAGE`: Discount to apply (default: 0.80 for 80% off)
- `MINIMUM_SALE_PRICE`: Minimum sale price (default: 120.00)
- `OUTPUT_FILENAME`: Default output filename

## How It Works

1. The script takes image URLs as input
2. For each image, it uses Google Gemini to extract:
   - Product name
   - Original price
   - Categories
   - Brand
   - Short description
   - Detailed description (as bullet points)
3. Applies the configured discount to the original price
4. Generates a WooCommerce-compatible CSV file with all required fields

## Troubleshooting

- Ensure your Google Gemini API key is valid and has sufficient quota
- Check the `wootomator.log` file for detailed error messages
- Make sure the image URLs are publicly accessible
- Verify that the output CSV file has write permissions

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is open source and available under the [MIT License](LICENSE).

## Acknowledgements

- [Flask](https://flask.palletsprojects.com/) - The web framework used
- [Google Gemini](https://ai.google.dev/) - For the AI-powered product extraction
- [Bootstrap](https://getbootstrap.com/) - For the responsive web interface
