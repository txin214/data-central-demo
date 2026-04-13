document.getElementById('product-id').style.display = 'none';




function removeComponent(componentId, componentName) {
    if (!confirm(`Are you sure you want to remove "${componentName}" from this product?`)) {
        return;
    }

    const productIdText = document.getElementById('product-id').textContent;
    const productId = parseInt(productIdText.split(':')[1].trim(), 10);

    if (!productId) {
        alert('Product ID not found.');
        return;
    }

    fetch('/product/remove_component/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            'product_id': productId,
            'component_id': componentId
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Component removed successfully!');
                // Refresh the page to show updated components
                location.reload();
            } else {
                alert('Failed to remove component.');
            }
        })
        .catch(error => console.error('Error:', error));
}

function performComponentSearch() {
    const query = document.getElementById('componentFilterIncludeProduct').value;
    const filterby = document.querySelector('input[name="componentFilterby"]:checked').value;

    if (!query.trim()) {
        alert('Please enter a search term.');
        return;
    }

    fetch(`/product/search_components/?q=${query}&filterby=${filterby}`, {
        method: 'GET',
    })
        .then(response => response.json())
        .then(data => {
            const resultsContainer = document.getElementById('component-search-results');
            resultsContainer.innerHTML = '';  // Clear previous results

            if (data.results.length > 0) {
                let tableContent = '<table class="ViewTable" style="width:80%; border: none">';
                tableContent += '<tr style="border: none; background-color: #2780e3; color: white; font-family: Arial, sans-serif; font-size: 14px; font-weight: normal;">';
                tableContent += '<th style="border: none; background-color: #2780e3; color: white; font-family: Arial, sans-serif; font-size: 14px; font-weight: normal;"><input type="checkbox" name="select_all_components" onclick="toggleAllComponents(this)" /></th>';
                tableContent += '<th style="border: none; background-color: #2780e3; color: white; font-family: Arial, sans-serif; font-size: 14px; font-weight: normal;">Part No</th>';
                tableContent += '<th style="border: none; background-color: #2780e3; color: white; font-family: Arial, sans-serif; font-size: 14px; font-weight: normal;">Description</th>';
                tableContent += '<th style="border: none; background-color: #2780e3; color: white; font-family: Arial, sans-serif; font-size: 14px; font-weight: normal;">Type</th>';
                tableContent += '<th style="border: none; background-color: #2780e3; color: white; font-family: Arial, sans-serif; font-size: 14px; font-weight: normal;">Unit Cost</th>';
                tableContent += '<th style="border: none; background-color: #2780e3; color: white; font-family: Arial, sans-serif; font-size: 14px; font-weight: normal;">Quantity</th>';
                tableContent += '</tr>';

                data.results.forEach(component => {
                    tableContent += `
            <tr>
                <td style="font-family: Arial, sans-serif; font-size: 14px;"><input type="checkbox" name="selected_components" value="${component.id}" /></td>
                <td style="font-family: Arial, sans-serif; font-size: 14px;">${component.part_no}</td>
                <td style="font-family: Arial, sans-serif; font-size: 14px;">${component.description}</td>
                <td style="font-family: Arial, sans-serif; font-size: 14px;">${component.product_type}</td>
                <td style="font-family: Arial, sans-serif; font-size: 14px;">${component.unit_total_cost !== null ? '$' + parseFloat(component.unit_total_cost).toFixed(2) : 'Not Available'}</td>
                <td style="font-family: Arial, sans-serif; font-size: 14px;"><input type="number" name="component_qty_${component.id}" value="1" min="0" step="0.001" style="width: 80px; height: 25px;" /></td>
            </tr>
        `;
                });

                tableContent += '</table>';
                tableContent += '<div style="margin-top: 10px;"><button type="button" class="btn btn-primary" onclick="submitComponents()">Add Selected Components</button></div>';
                resultsContainer.innerHTML = tableContent;

            } else {
                resultsContainer.innerHTML = '<table class="ViewTable" style="border: none"><tr style="border: none"><td colspan="6" class="table-title" style="border: none">No products were found.</td></tr></table>';
            }
        })
        .catch(error => console.error('Error:', error));
}

function toggleAllComponents(checkbox) {
    const componentCheckboxes = document.querySelectorAll('input[name="selected_components"]');
    componentCheckboxes.forEach(cb => {
        cb.checked = checkbox.checked;
    });
}

function submitComponents() {
    const selectedComponents = Array.from(document.querySelectorAll('input[name="selected_components"]:checked'))
        .map(input => {
            const componentId = input.value;
            const qtyInput = document.querySelector(`input[name="component_qty_${componentId}"]`);
            const qty = qtyInput ? parseFloat(qtyInput.value) || 1 : 1;
            return { id: componentId, qty: qty };
        });
        
    const productIdElement = document.getElementById('product-id');
    if (!productIdElement) {
        alert('Product ID element not found. Please refresh the page and try again.');
        return;
    }
    
    const productIdText = productIdElement.textContent;
        const productId = parseInt(productIdText.split(':')[1].trim(), 10);

    console.log('Product ID:', productId);
    console.log('Selected Components:', selectedComponents);

    if (!productId || selectedComponents.length === 0) {
        alert('Please select a valid product and at least one component.');
        return;
    }

    const requestData = {
        'product_id': productId,
        'components': selectedComponents
    };
    
    console.log('Request data:', requestData);
    console.log('CSRF Token:', getCookie('csrftoken'));

    fetch('/product/add_components/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify(requestData)
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update the hidden components field to preserve selections during form submission
                const componentsField = document.getElementById('components_field');
                if (componentsField) {
                    // Get current components and add new ones
                    const currentComponents = componentsField.value ? componentsField.value.split(',').filter(id => id.trim()) : [];
                    const newComponentEntries = selectedComponents.map(comp => `${comp.id}:${comp.qty}`);
                    const newComponents = [...new Set([...currentComponents, ...newComponentEntries])];
                    componentsField.value = newComponents.join(',');
                }
                
                // Show detailed success message
                let message = 'Components processed successfully!';
                if (data.added && data.added.length > 0) {
                    message += '\n\nAdded: ' + data.added.join(', ');
                }
                if (data.skipped && data.skipped.length > 0) {
                    message += '\n\nQuantity Added: ' + data.skipped.join(', ');
                }
                alert(message);
                
                // Refresh the page to show updated components
                location.reload();
            } else {
                alert('Failed to add components: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Failed to add components: ' + error.message);
        });
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

