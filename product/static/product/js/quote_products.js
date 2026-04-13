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
    // Select all the quantity inputs
    const quantityInputs = document.querySelectorAll('input[name^="quantities["]');
    
    // Listen for changes on each quantity input
    quantityInputs.forEach(input => {
        input.addEventListener('change', function () {
            // Debugging step to check the current value
            console.log('Changed quantity for product ID ' + this.name + ' to:', this.value);

            // If quantity is less than 1, set it to 1 (to prevent invalid quantity)
            if (parseInt(this.value) < 1) {
                this.value = 1;
            }
        });
    });

    // Handle checkbox click to enable/disable the quantity field
    const checkboxes = document.querySelectorAll('input[name="products[]"]');
    
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function () {
            // Find the corresponding quantity input using the product ID
            const quantityInput = this.closest('tr').querySelector('input[name="quantities[' + this.value + ']"]');
            
            if (this.checked) {
                // Ensure quantity input is enabled if the checkbox is checked
                quantityInput.disabled = false;
                if (quantityInput.value == '') {
                    quantityInput.value = 1;  // Set default value if empty
                }
            } else {
                // Disable quantity input if checkbox is unchecked
                quantityInput.disabled = true;
            }
        });
    });
});