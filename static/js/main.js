// Main JavaScript for WooCommerce Product Generator

document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const urlForm = document.getElementById('urlForm');
    const fileForm = document.getElementById('fileForm');
    const processingSpinner = document.getElementById('processingSpinner');
    const resultsSection = document.getElementById('resultsSection');
    const productsContainer = document.getElementById('productsContainer');
    const downloadCsvBtn = document.getElementById('downloadCsv');
    
    // State
    let isSubmitting = false;
    let currentProducts = [];
    
    // Initialize event listeners
    function initEventListeners() {
        // URL Form Submission
        if (urlForm) {
            urlForm.addEventListener('submit', handleFormSubmit);
        }
        
        // File Form Submission
        if (fileForm) {
            fileForm.addEventListener('submit', handleFormSubmit);
            
            // File upload handling
            const dropZone = document.getElementById('dropZone');
            const fileInput = document.getElementById('fileInput');
            
            if (dropZone && fileInput) {
                // Drag and drop handling
                ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                    dropZone.addEventListener(eventName, preventDefaults, false);
                });
                
                ['dragenter', 'dragover'].forEach(eventName => {
                    dropZone.addEventListener(eventName, highlight, false);
                });
                
                ['dragleave', 'drop'].forEach(eventName => {
                    dropZone.addEventListener(eventName, unhighlight, false);
                });
                
                dropZone.addEventListener('drop', handleDrop, false);
                dropZone.addEventListener('click', () => fileInput.click());
                fileInput.addEventListener('change', handleFileSelect);
            }
        }
        
        // Download CSV button
        if (downloadCsvBtn) {
            downloadCsvBtn.addEventListener('click', handleCsvDownload);
        }
        
        // Initialize tooltips
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(tooltipTriggerEl => {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // Form submission handler
    async function handleFormSubmit(e) {
        e.preventDefault();
        
        if (isSubmitting) return;
        isSubmitting = true;
        setLoading(true);
        
        const form = e.target;
        const formData = new FormData();
        
        // For URL form
        if (form.id === 'urlForm') {
            const urls = document.getElementById('imageUrls').value;
            if (!urls.trim()) {
                showError('Please enter at least one URL');
                setLoading(false);
                isSubmitting = false;
                return;
            }
            formData.append('urls', urls);
        } 
        // For file form
        else if (form.id === 'fileForm') {
            const fileInput = document.getElementById('fileInput');
            if (fileInput.files.length === 0) {
                showError('Please select a file to upload');
                setLoading(false);
                isSubmitting = false;
                return;
            }
            formData.append('file', fileInput.files[0]);
        }
        
        // Get sizes from checkboxes
        const sizeCheckboxes = document.querySelectorAll('.size-checkbox:checked');
        const sizes = Array.from(sizeCheckboxes).map(cb => cb.value);
        
        // Add sizes to form data
        formData.append('sizes', JSON.stringify(sizes));
        
        try {
            // Ensure API_BASE_URL is defined
            const baseUrl = window.API_BASE_URL || '';
            const apiUrl = `${baseUrl}/process`;
            
            console.log('Sending request to:', apiUrl);
            
            const response = await fetch(apiUrl, {
                method: 'POST',
                body: formData,
                credentials: 'same-origin' // Include cookies if any
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || 'Failed to process request');
            }
            
            const data = await response.json();
            
            if (!data.success || !data.products || data.products.length === 0) {
                throw new Error(data.error || 'No products were generated');
            }
            
            // Store products for later use
            currentProducts = data.products;
            
            // Render products
            renderProducts(data.products);
            
            // Show results section
            resultsSection.style.display = 'block';
            
            // Enable download button
            if (downloadCsvBtn) {
                downloadCsvBtn.disabled = false;
            }
            
            // Scroll to results
            resultsSection.scrollIntoView({ behavior: 'smooth' });
            
        } catch (error) {
            console.error('Error:', error);
            showError(error.message || 'An error occurred while processing your request');
        } finally {
            setLoading(false);
            isSubmitting = false;
        }
    }
    
    // Render products in the table
    function renderProducts(products) {
        if (!productsContainer) return;
        
        productsContainer.innerHTML = '';
        
        products.forEach(product => {
            const row = document.createElement('tr');
            row.className = 'product-row';
            row.innerHTML = `
                <td>
                    <img src="${product.image || 'https://via.placeholder.com/100?text=No+Image'}" 
                         class="img-thumbnail" 
                         style="max-width: 80px;"
                         alt="${product.name || 'Product Image'}">
                </td>
                <td>${product.name || 'No Name'}</td>
                <td>${product.short_description || 'No description'}</td>
                <td>$${product.regular_price || '0.00'}</td>
                <td>$${product.sale_price || '0.00'}</td>
                <td>${product.sku || 'N/A'}</td>
                <td class="size-selection">
                    ${generateSizeCheckboxes(product.sku, ['S', 'M', 'L', 'XL'])}
                </td>
                <td>
                    <button class="btn btn-sm btn-outline-primary toggle-all-sizes" 
                            type="button" 
                            data-bs-toggle="tooltip" 
                            title="Toggle all sizes">
                        <i class="bi bi-check2-all"></i>
                    </button>
                </td>`;
                
            productsContainer.appendChild(row);
        });
        
        // Initialize size toggle buttons
        initSizeToggleButtons();
    }
    
    // Generate size checkboxes HTML
    function generateSizeCheckboxes(baseSku, sizes) {
        return sizes.map(size => `
            <div class="form-check form-check-inline">
                <input class="form-check-input product-size-checkbox" 
                       type="checkbox" 
                       id="${baseSku}-${size}" 
                       value="${size}" 
                       data-sku="${baseSku}-${size}"
                       checked>
                <label class="form-check-label" for="${baseSku}-${size}">
                    ${size}
                </label>
            </div>
        `).join('');
    }
    
    // Initialize size toggle buttons
    function initSizeToggleButtons() {
        document.querySelectorAll('.toggle-all-sizes').forEach(button => {
            button.addEventListener('click', function() {
                const row = this.closest('tr');
                const checkboxes = row.querySelectorAll('.product-size-checkbox');
                const allChecked = Array.from(checkboxes).every(checkbox => checkbox.checked);
                
                checkboxes.forEach(checkbox => {
                    checkbox.checked = !allChecked;
                });
                
                const icon = this.querySelector('i');
                if (allChecked) {
                    icon.className = 'bi bi-x';
                    this.setAttribute('title', 'Select all');
                } else {
                    icon.className = 'bi bi-check2-all';
                    this.setAttribute('title', 'Deselect all');
                }
                
                // Update tooltip
                const tooltip = bootstrap.Tooltip.getInstance(this);
                if (tooltip) {
                    tooltip.dispose();
                    new bootstrap.Tooltip(this);
                }
            });
        });
    }
    
    // Handle CSV download
    async function handleCsvDownload() {
        if (!currentProducts || currentProducts.length === 0) {
            showError('No products available to download');
            return;
        }
        
        setLoading(true);
        
        try {
            // Collect selected sizes for each product
            const productsWithSizes = currentProducts.map(product => ({
                ...product,
                selectedSizes: Array.from(document.querySelectorAll(`#${product.sku} .product-size-checkbox:checked`))
                    .map(checkbox => checkbox.value)
            }));
            
            console.log('Sending products to generate CSV:', productsWithSizes);
            
            // Ensure API_BASE_URL is defined
            const baseUrl = window.API_BASE_URL || '';
            const apiUrl = `${baseUrl}/generate_csv`;
            
            console.log('Sending request to generate CSV:', apiUrl);
            
            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    products: productsWithSizes,
                    sizes: Array.from(document.querySelectorAll('.size-checkbox:checked')).map(cb => cb.value)
                }),
                credentials: 'same-origin' // Include cookies if any
            });
            
            console.log('CSV generation response status:', response.status);
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('Error response:', errorText);
                let errorData;
                try {
                    errorData = JSON.parse(errorText);
                } catch (e) {
                    throw new Error(`Failed to generate CSV: ${response.status} ${response.statusText}`);
                }
                throw new Error(errorData.error || 'Failed to generate CSV');
            }
            
            const data = await response.json();
            console.log('CSV generation response data:', data);
            
            if (!data.success) {
                throw new Error(data.error || 'Failed to generate CSV');
            }
            
            if (!data.download_url) {
                throw new Error('No download URL provided in response');
            }
            
            console.log('Triggering download with URL:', data.download_url);
            
            // Create a hidden link and trigger the download
            const link = document.createElement('a');
            link.href = data.download_url;
            link.download = ''; // Let the browser determine the filename
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
        } catch (error) {
            console.error('Error downloading CSV:', error);
            showError(error.message || 'Failed to download CSV');
        } finally {
            setLoading(false);
        }
    }
    
    // Helper functions
    function setLoading(isLoading) {
        if (isLoading) {
            processingSpinner.style.display = 'block';
            document.querySelectorAll('button[type="submit"]').forEach(btn => {
                btn.disabled = true;
            });
        } else {
            processingSpinner.style.display = 'none';
            document.querySelectorAll('button[type="submit"]').forEach(btn => {
                btn.disabled = false;
            });
        }
    }
    
    function showError(message) {
        // Remove any existing alerts
        const existingAlert = document.querySelector('.alert');
        if (existingAlert) {
            existingAlert.remove();
        }
        
        // Create and show new alert
        const alert = document.createElement('div');
        alert.className = 'alert alert-danger alert-dismissible fade show';
        alert.role = 'alert';
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        const container = document.querySelector('.container');
        if (container) {
            container.prepend(alert);
        }
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    }
    
    // File upload helpers
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    function highlight() {
        dropZone.classList.add('border-primary');
    }
    
    function unhighlight() {
        dropZone.classList.remove('border-primary');
    }
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        if (files.length) {
            fileInput.files = files;
            handleFileSelect({ target: { files } });
        }
    }
    
    function handleFileSelect(e) {
        const files = e.target.files;
        const file = files[0];
        
        if (file) {
            const fileName = document.getElementById('fileName');
            if (fileName) {
                fileName.textContent = `Selected file: ${file.name}`;
            }
            
            const processBtn = document.getElementById('processFileBtn');
            if (processBtn) {
                processBtn.disabled = false;
            }
        }
    }
    
    // Initialize the application
    initEventListeners();
});
