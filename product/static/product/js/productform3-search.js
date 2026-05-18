(function () {
    const el = document.getElementById('product-id');
    if (el) el.setAttribute('hidden', '');
})();

function getProductPk() {
    const el = document.getElementById('product-id');
    if (!el) return NaN;
    const pk = el.getAttribute('data-product-pk');
    if (pk != null && pk !== '') {
        const n = parseInt(pk, 10);
        return Number.isFinite(n) ? n : NaN;
    }
    const text = el.textContent || '';
    const colon = text.indexOf(':');
    if (colon >= 0) {
        return parseInt(text.slice(colon + 1).trim(), 10);
    }
    return NaN;
}

function setComponentsHidden(value) {
    const field = document.getElementById('components_field');
    if (field) field.value = value;
}

function renderSelectedComponents(rows) {
    const tbody = document.getElementById('selected-components-tbody');
    if (!tbody) return;

    tbody.textContent = '';

    if (!rows || rows.length === 0) {
        const tr = document.createElement('tr');
        tr.style.border = 'none';
        const td = document.createElement('td');
        td.colSpan = 6;
        td.className = 'table-title';
        td.style.border = 'none';
        td.textContent = 'No components were found.';
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
    }

    const headerTr = document.createElement('tr');
    headerTr.style.border = 'none';
    ['Component', 'Description', 'Type', 'Unit Cost', 'Quantity', 'Action'].forEach(function (label) {
        const td = document.createElement('td');
        td.style.border = 'none';
        const b = document.createElement('b');
        b.textContent = label;
        td.appendChild(b);
        headerTr.appendChild(td);
    });
    tbody.appendChild(headerTr);

    rows.forEach(function (row) {
        const tr = document.createElement('tr');
        tr.style.border = 'none';

        ['part_no', 'description', 'product_type'].forEach(function (key) {
            const td = document.createElement('td');
            td.style.border = 'none';
            td.textContent = row[key] != null ? String(row[key]) : '';
            tr.appendChild(td);
        });

        const tdCost = document.createElement('td');
        tdCost.style.border = 'none';
        if (row.unit_total_cost != null && row.unit_total_cost !== '') {
            tdCost.textContent = '$' + Number(row.unit_total_cost).toFixed(2);
        } else {
            tdCost.textContent = 'Not Available';
        }
        tr.appendChild(tdCost);

        const tdQty = document.createElement('td');
        tdQty.style.border = 'none';
        const q = parseFloat(row.qty);
        tdQty.textContent = Number.isFinite(q) ? q.toFixed(3) : String(row.qty);
        tr.appendChild(tdQty);

        const tdBtn = document.createElement('td');
        tdBtn.style.border = 'none';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-sm btn-outline-danger';
        btn.style.padding = '2px 6px';
        btn.style.fontSize = '11px';
        btn.style.height = '30px';
        btn.innerHTML = '<i class="fa-solid fa-trash"></i> Remove';
        const cid = row.component_id;
        const pname = row.part_no || '';
        btn.addEventListener('click', function () {
            removeComponent(cid, pname);
        });
        tdBtn.appendChild(btn);
        tr.appendChild(tdBtn);

        tbody.appendChild(tr);
    });
}

function clearComponentSearchSelection() {
    document.querySelectorAll('input[name="selected_components"]').forEach(function (cb) {
        cb.checked = false;
    });
    const selAll = document.querySelector('input[name="select_all_components"]');
    if (selAll) selAll.checked = false;
}

function removeComponent(componentId, componentName) {
    if (!confirm('Are you sure you want to remove "' + (componentName || 'this component') + '" from this product?')) {
        return;
    }

    const productId = getProductPk();

    if (!Number.isFinite(productId) || productId < 1) {
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
            product_id: productId,
            component_id: componentId
        })
    })
        .then(function (response) {
            return response.json().then(function (data) {
                return { ok: response.ok, data: data };
            });
        })
        .then(function (result) {
            if (result.ok && result.data.success) {
                location.reload();
            } else {
                alert('Failed to remove component.' + (result.data.error ? ' ' + result.data.error : ''));
            }
        })
        .catch(function (error) {
            console.error('Error:', error);
            alert('Failed to remove component.');
        });
}

function performComponentSearch() {
    const query = document.getElementById('componentFilterIncludeProduct').value;
    const filterby = document.querySelector('input[name="componentFilterby"]:checked').value;

    if (!query.trim()) {
        alert('Please enter a search term.');
        return;
    }

    fetch('/product/search_components/?q=' + encodeURIComponent(query) + '&filterby=' + encodeURIComponent(filterby), {
        method: 'GET'
    })
        .then(function (response) {
            return response.json();
        })
        .then(function (data) {
            const resultsContainer = document.getElementById('component-search-results');
            resultsContainer.innerHTML = '';

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

                data.results.forEach(function (component) {
                    tableContent +=
                        '<tr>' +
                        '<td style="font-family: Arial, sans-serif; font-size: 14px;"><input type="checkbox" name="selected_components" value="' +
                        component.id +
                        '" /></td>' +
                        '<td style="font-family: Arial, sans-serif; font-size: 14px;">' +
                        escapeHtml(component.part_no) +
                        '</td>' +
                        '<td style="font-family: Arial, sans-serif; font-size: 14px;">' +
                        escapeHtml(component.description) +
                        '</td>' +
                        '<td style="font-family: Arial, sans-serif; font-size: 14px;">' +
                        escapeHtml(component.product_type) +
                        '</td>' +
                        '<td style="font-family: Arial, sans-serif; font-size: 14px;">' +
                        (component.unit_total_cost !== null ? '$' + parseFloat(component.unit_total_cost).toFixed(2) : 'Not Available') +
                        '</td>' +
                        '<td style="font-family: Arial, sans-serif; font-size: 14px;"><input type="number" name="component_qty_' +
                        component.id +
                        '" value="1" min="0" step="0.001" style="width: 80px; height: 25px;" /></td>' +
                        '</tr>';
                });

                tableContent += '</table>';
                tableContent +=
                    '<div style="margin-top: 10px;"><button type="button" class="btn btn-primary" onclick="submitComponents()">Add Selected Components</button></div>';
                resultsContainer.innerHTML = tableContent;
            } else {
                resultsContainer.innerHTML =
                    '<table class="ViewTable" style="border: none"><tr style="border: none"><td colspan="6" class="table-title" style="border: none">No products were found.</td></tr></table>';
            }
        })
        .catch(function (error) {
            console.error('Error:', error);
        });
}

function escapeHtml(text) {
    if (text == null || text === '') return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function toggleAllComponents(checkbox) {
    const componentCheckboxes = document.querySelectorAll('input[name="selected_components"]');
    componentCheckboxes.forEach(function (cb) {
        cb.checked = checkbox.checked;
    });
}

function submitComponents() {
    const selectedComponents = Array.from(document.querySelectorAll('input[name="selected_components"]:checked')).map(function (input) {
        const componentId = input.value;
        const qtyInput = document.querySelector('input[name="component_qty_' + componentId + '"]');
        const qty = qtyInput ? parseFloat(qtyInput.value) || 1 : 1;
        return { id: componentId, qty: qty };
    });

    const productId = getProductPk();

    if (!Number.isFinite(productId) || productId < 1 || selectedComponents.length === 0) {
        alert('Please select a valid product and at least one component.');
        return;
    }

    const requestData = {
        product_id: productId,
        components: selectedComponents
    };

    fetch('/product/add_components/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify(requestData)
    })
        .then(function (response) {
            return response.json().then(function (data) {
                return { ok: response.ok, status: response.status, data: data };
            });
        })
        .then(function (result) {
            const data = result.data;
            if (!result.ok || !data.success) {
                alert('Failed to add components: ' + (data && data.error ? data.error : 'HTTP ' + result.status));
                return;
            }

            renderSelectedComponents(data.selected_components);
            if (data.components_hidden != null) {
                setComponentsHidden(data.components_hidden);
            }
            clearComponentSearchSelection();

            const tb = document.getElementById('selected-components-tbody');
            if (tb && tb.scrollIntoView) {
                tb.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        })
        .catch(function (error) {
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
            if (cookie.substring(0, name.length + 1) === name + '=') {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
