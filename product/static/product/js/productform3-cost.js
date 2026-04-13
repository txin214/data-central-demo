var laborRate = 0; // Global variable for labor rate - set to 0 for now
var installRate = 0; // Global variable for install rate - set to 0 for now

function validateMultiplier(inputElement, fieldName) {
    var value = inputElement.value.trim();
    
    // Allow empty values
    if (value === '') {
        return true;
    }
    
    // Allow partial decimal input (e.g., "0.", "0.8", "0.80")
    // Don't validate until user finishes typing
    if (value === '0' || value === '0.' || value.endsWith('.')) {
        return true; // Allow partial input
    }
    
    // Only validate complete numbers
    var numValue = parseFloat(value);
    if (isNaN(numValue) || numValue <= 0 || numValue > 1) {
        alert(fieldName + " must be empty or a number between 0 and 1 (inclusive).");
        inputElement.value = '';
        return false;
    }
    
    return true;
}

function updateUnitTotalCost() {
    // Get the actual DOM elements to verify we're reading from the right fields
    var materialCostElement = document.getElementById('id_unit_material_cost');
    var baseCostElement = document.getElementById('id_unit_base_cost');
    var laborCostElement = document.getElementById('id_unit_labor_cost');
    
    // Get the values and log them for debugging
    var materialCost = parseFloat(materialCostElement ? materialCostElement.value : 0) || 0;
    var baseCost = parseFloat(baseCostElement ? baseCostElement.value : 0) || 0;
    var laborCost = parseFloat(laborCostElement ? laborCostElement.value : 0) || 0;
    
    console.log('=== COST CALCULATION DEBUG ===');
    console.log('Material Cost Element:', materialCostElement);
    console.log('Material Cost Element ID:', materialCostElement ? materialCostElement.id : 'NOT FOUND');
    console.log('Material Cost Element Value:', materialCostElement ? materialCostElement.value : 'NOT FOUND');
    console.log('Base Cost Element:', baseCostElement);
    console.log('Base Cost Element ID:', baseCostElement ? baseCostElement.id : 'NOT FOUND');
    console.log('Base Cost Element Value:', baseCostElement ? baseCostElement.value : 'NOT FOUND');
    console.log('Labor Cost Element:', laborCostElement);
    console.log('Labor Cost Element ID:', laborCostElement ? laborCostElement.id : 'NOT FOUND');
    console.log('Labor Cost Element Value:', laborCostElement ? laborCostElement.value : 'NOT FOUND');
    
    console.log('Parsed Values:', {materialCost, baseCost, laborCost});
    
    var totalCost = baseCost + laborCost + materialCost;
    console.log('Calculated Total Cost:', totalCost);
    
    // Update the total cost field
    var totalCostElement = document.getElementById('id_unit_total_cost');
    if (totalCostElement) {
        totalCostElement.value = totalCost.toFixed(2);
        console.log('Updated Total Cost Field:', totalCostElement.value);
    } else {
        console.error('Total Cost Field NOT FOUND!');
    }
    
    console.log('=== END COST CALCULATION DEBUG ===');
    
    updateRetailSell();
    updateBuilderSell();
    updateSurplusSell();
}

function updateBulkTotalCost() {
    var bulkMaterialCost = parseFloat(document.getElementById('id_bulk_material_cost').value) || 0;
    var bulkLaborCost = parseFloat(document.getElementById('id_bulk_labor_cost').value) || 0;
    var bulkTotalCost = bulkMaterialCost + bulkLaborCost;
    document.getElementById('id_bulk_total_cost').value = bulkTotalCost.toFixed(2);
}

function updateRetailSell() {
    var totalCost = parseFloat(document.getElementById('id_unit_total_cost').value) || 0;
    var multiplierInput = document.getElementById('id_retail_sell_multiplier');
    var retailSellInput = document.getElementById('id_retail_sell');
    
    console.log('Updating retail sell:', {totalCost, multiplierInput: multiplierInput?.value, retailSellInput: retailSellInput?.value});
    
    // Only calculate if retail sell field is empty (respect manual entries)
    if (!retailSellInput.value.trim()) {
        var multiplier = parseFloat(multiplierInput.value);
        if (!isNaN(multiplier) && multiplier > 0) {
            var retailSell = totalCost / multiplier;
            retailSellInput.value = retailSell.toFixed(2);
            console.log('Retail sell calculated:', retailSell);
        } else {
            retailSellInput.value = '';
            console.log('Retail sell cleared - invalid multiplier');
        }
    } else {
        console.log('Retail sell field has manual value, not overwriting');
    }
}

function updateBuilderSell() {
    var totalCost = parseFloat(document.getElementById('id_unit_total_cost').value) || 0;
    var multiplierInput = document.getElementById('id_builder_sell_multiplier');
    var builderSellInput = document.getElementById('id_builder_sell');
    
    console.log('Updating builder sell:', {totalCost, multiplierInput: multiplierInput?.value, builderSellInput: builderSellInput?.value});
    
    // Only calculate if builder sell field is empty (respect manual entries)
    if (!builderSellInput.value.trim()) {
        var multiplier = parseFloat(multiplierInput.value);
        if (!isNaN(multiplier) && multiplier > 0) {
            var builderSell = totalCost / multiplier;
            builderSellInput.value = builderSell.toFixed(2);
            console.log('Builder sell calculated:', builderSell);
        } else {
            builderSellInput.value = '';
            console.log('Builder sell cleared - invalid multiplier');
        }
    } else {
        console.log('Builder sell field has manual value, not overwriting');
    }
}

function updateSurplusSell() {
    var totalCost = parseFloat(document.getElementById('id_unit_total_cost').value) || 0;
    var multiplierInput = document.getElementById('id_surplus_sell_multiplier');
    console.log('Updating surplus sell:', {totalCost, multiplierInput: multiplierInput?.value});
    
    var multiplier = parseFloat(multiplierInput.value);
    if (!isNaN(multiplier) && multiplier > 0) {
        var surplusSell = totalCost / multiplier;
        document.getElementById('id_surplus_sell').value = surplusSell.toFixed(2);
        console.log('Surplus sell calculated:', surplusSell);
    } else {
        document.getElementById('id_surplus_sell').value = '';
        console.log('Surplus sell cleared - invalid multiplier');
    }
}

document.addEventListener('DOMContentLoaded', function () {
    console.log('DOM loaded, setting up form event listeners');
    
    // Individual Cost Inputs
    var materialCostInput = document.getElementById('id_unit_material_cost');
    var baseCostInput = document.getElementById('id_unit_base_cost');
    var laborCostInput = document.getElementById('id_unit_labor_cost');
    var retailMultiplierInput = document.getElementById('id_retail_sell_multiplier');
    var builderMultiplierInput = document.getElementById('id_builder_sell_multiplier');
    var surplusMultiplierInput = document.getElementById('id_surplus_sell_multiplier');
    
    console.log('Form fields found:', {
        materialCostInput: !!materialCostInput,
        baseCostInput: !!baseCostInput,
        laborCostInput: !!laborCostInput,
        retailMultiplierInput: !!retailMultiplierInput,
        builderMultiplierInput: !!builderMultiplierInput,
        surplusMultiplierInput: !!surplusMultiplierInput
    });
    
    // Bulk Cost Inputs
    var bulkMaterialCostInput = document.getElementById('id_bulk_material_cost');
    var bulkLaborCostInput = document.getElementById('id_bulk_labor_cost');
    
    // Event Listeners
    if (materialCostInput) materialCostInput.addEventListener('input', updateUnitTotalCost);
    if (baseCostInput) baseCostInput.addEventListener('input', updateUnitTotalCost);
    if (laborCostInput) laborCostInput.addEventListener('input', updateUnitTotalCost);
    if (retailMultiplierInput) {
        retailMultiplierInput.addEventListener('input', updateRetailSell);
        retailMultiplierInput.addEventListener('blur', function() {
            // Validate on blur (when user finishes typing)
            validateMultiplier(this, "Retail sell multiplier");
        });
    }
    if (builderMultiplierInput) {
        builderMultiplierInput.addEventListener('input', updateBuilderSell);
        builderMultiplierInput.addEventListener('blur', function() {
            // Validate on blur (when user finishes typing)
            validateMultiplier(this, "Builder sell multiplier");
        });
    }
    if (surplusMultiplierInput) {
        surplusMultiplierInput.addEventListener('input', updateSurplusSell);
        surplusMultiplierInput.addEventListener('blur', function() {
            // Validate on blur (when user finishes typing)
            validateMultiplier(this, "Surplus sell multiplier");
        });
    }
    if (bulkMaterialCostInput) bulkMaterialCostInput.addEventListener('input', updateBulkTotalCost);
    if (bulkLaborCostInput) bulkLaborCostInput.addEventListener('input', updateBulkTotalCost);
    
    // Add event listeners to price fields to prevent multiplier overwrites
    var retailSellInput = document.getElementById('id_retail_sell');
    var builderSellInput = document.getElementById('id_builder_sell');
    
    if (retailSellInput) {
        retailSellInput.addEventListener('input', function() {
            console.log('Retail sell manually entered, preventing multiplier overwrite');
        });
    }
    
    if (builderSellInput) {
        builderSellInput.addEventListener('input', function() {
            console.log('Builder sell manually entered, preventing multiplier overwrite');
        });
    }
    
    console.log('Event listeners attached, running initial updates');
    
    // Initial Updates
    updateUnitTotalCost();
    updateBulkTotalCost();
    
    console.log('Initial updates completed');
});
