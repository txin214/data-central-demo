function toggleAllPrices() {
    const optionalColumns = document.querySelectorAll('.optional-column');
    const optionalHeaders = document.querySelectorAll('.optional-header');
    const button = document.querySelector('.toggle-price-btn');
    
    // Check if any of the optional columns are currently visible
    const isVisible = optionalColumns[0].style.display === 'table-cell';
    
    if (isVisible) {
        // Hide optional columns
        optionalColumns.forEach(col => col.style.display = 'none');
        optionalHeaders.forEach(header => header.style.display = 'none');
        button.textContent = 'Show Optional Prices';  // Change button text
    } else {
        // Show optional columns
        optionalColumns.forEach(col => col.style.display = 'table-cell');
        optionalHeaders.forEach(header => header.style.display = 'table-cell');
        button.textContent = 'Hide Optional Prices';  // Change button text
    }
}

document.addEventListener('DOMContentLoaded', function () {
    // Quantity > 0 means "add this product"; keep 0 allowed for rows not being added.
    const quantityInputs = document.querySelectorAll('input[name^="quantities["]');
    quantityInputs.forEach(input => {
        input.addEventListener('change', function () {
            const quantity = parseInt(this.value, 10);
            if (isNaN(quantity) || quantity < 0) {
                this.value = 0;
            }
        });
    });
});
