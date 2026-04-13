document.addEventListener("DOMContentLoaded", () => {
    const container = document.querySelector('.category-container');

    container.addEventListener('click', (event) => {
        const toggle = event.target.closest('.collapse-toggle');
        if (!toggle) return;

        event.preventDefault();
        const target = document.getElementById(toggle.dataset.target);
        if (!target) return;

        const isCategory = toggle.closest('.category-list');
        const isSubcategory1 = toggle.closest('.subcategory1-list');
        const isSubcategory2 = toggle.closest('.subcategory2-list');
        const isColor = toggle.closest('.color-list');
        const isAddForm = toggle.dataset.target.includes('add-');

        // Handle different column types
        if (isCategory && !isAddForm) {
            hideAllContent();
        } else if (isSubcategory1 && !isAddForm) {
            hideSubcategory2Content();
        } else if (isSubcategory2 && !isAddForm) {
            hideColorContent();
        }

        toggleTargetDisplay(toggle, target);
    });

    function hideAllContent() {
        document.querySelectorAll('.collapse-content').forEach(content => {
            content.style.display = "none";
        });
        document.querySelectorAll('.collapse-toggle').forEach(toggle => {
            toggle.classList.remove('active');
        });
    }

    function hideSubcategory2Content() {
        const subcategory1List = document.querySelector('.subcategory1-list');
        if (subcategory1List) {
            subcategory1List.querySelectorAll('.collapse-toggle').forEach(subToggle => {
                const subTarget = document.getElementById(subToggle.dataset.target);
                if (subToggle !== event.target.closest('.collapse-toggle') && subTarget) {
                    subTarget.style.display = "none";
                    subToggle.classList.remove('active');
                }
            });
        }
    }

    function hideColorContent() {
        const subcategory2List = document.querySelector('.subcategory2-list');
        if (subcategory2List) {
            subcategory2List.querySelectorAll('.collapse-toggle').forEach(subToggle => {
                const subTarget = document.getElementById(subToggle.dataset.target);
                if (subToggle !== event.target.closest('.collapse-toggle') && subTarget) {
                    subTarget.style.display = "none";
                    subToggle.classList.remove('active');
                }
            });
        }
    }

    function toggleTargetDisplay(toggle, target) {
        const isCurrentlyActive = toggle.classList.contains('active');

        if (isCurrentlyActive) {
            target.style.display = "none";
            toggle.classList.remove('active');
        } else {
            target.style.display = "block";
            toggle.classList.add('active');
        }
    }

    // Add smooth scrolling for long lists
    const listGroups = document.querySelectorAll('.list-group');
    listGroups.forEach(listGroup => {
        listGroup.addEventListener('scroll', (e) => {
            // Add shadow effect when scrolling
            if (e.target.scrollTop > 0) {
                e.target.style.boxShadow = 'inset 0 2px 4px rgba(0,0,0,0.1)';
            } else {
                e.target.style.boxShadow = 'none';
            }
        });
    });

    // Add hover effects for color previews
    const colorPreviews = document.querySelectorAll('.color-preview');
    colorPreviews.forEach(preview => {
        preview.addEventListener('mouseenter', () => {
            preview.style.transform = 'scale(1.2)';
            preview.style.transition = 'transform 0.2s ease';
        });
        
        preview.addEventListener('mouseleave', () => {
            preview.style.transform = 'scale(1)';
        });
    });

    // Add form validation feedback
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', (e) => {
            const inputs = form.querySelectorAll('input[type="text"]');
            let isValid = true;
            
            inputs.forEach(input => {
                if (!input.value.trim()) {
                    isValid = false;
                    input.classList.add('is-invalid');
                } else {
                    input.classList.remove('is-invalid');
                }
            });
            
            if (!isValid) {
                e.preventDefault();
                // Show error message
                const errorDiv = form.querySelector('.error-message') || document.createElement('div');
                errorDiv.className = 'error-message text-danger mt-2';
                errorDiv.textContent = 'Please fill in all required fields.';
                if (!form.querySelector('.error-message')) {
                    form.appendChild(errorDiv);
                }
            }
        });
    });

    // Add loading states for buttons
    const submitButtons = document.querySelectorAll('button[type="submit"]');
    submitButtons.forEach(button => {
        button.addEventListener('click', () => {
            const originalText = button.innerHTML;
            button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Processing...';
            button.disabled = true;
            
            // Reset after a delay (in case of form validation failure)
            setTimeout(() => {
                button.innerHTML = originalText;
                button.disabled = false;
            }, 3000);
        });
    });

    // CSRF helper for AJAX
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
    const csrftoken = getCookie('csrftoken');

    // AJAX add handlers for category, subcategory1, subcategory2, color
    document.body.addEventListener('submit', function(e) {
        const form = e.target;
        console.log('Form submit event detected:', form);
        if (form.matches('[action*="ajax/add-category"]') ||
            form.matches('[action*="ajax/add-subcategory1"]') ||
            form.matches('[action*="ajax/add-subcategory2"]') ||
            form.matches('[action*="ajax/add-color"]')) {
            console.log('AJAX add form matched:', form.action);
            e.preventDefault();
            const url = form.action;
            const formData = new FormData(form);
            const submitBtn = form.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Processing...';
            submitBtn.disabled = true;
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrftoken
                },
                body: formData
            })
            .then(res => res.json().then(data => ({status: res.status, data})))
            .then(({status, data}) => {
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
                if (status === 200 && data.success) {
                    // Add to DOM (simple append, or reload part of the list)
                    location.reload();
                } else {
                    // Show errors
                    let errorDiv = form.querySelector('.error-message');
                    if (!errorDiv) {
                        errorDiv = document.createElement('div');
                        errorDiv.className = 'error-message text-danger mt-2';
                        form.appendChild(errorDiv);
                    }
                    errorDiv.textContent = data.errors ? Object.values(data.errors).flat().join(' ') : 'Error occurred.';
                }
            })
            .catch(() => {
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
                let errorDiv = form.querySelector('.error-message');
                if (!errorDiv) {
                    errorDiv = document.createElement('div');
                    errorDiv.className = 'error-message text-danger mt-2';
                    form.appendChild(errorDiv);
                }
                errorDiv.textContent = 'Network or server error.';
            });
        } else {
            console.log('Form submit did not match AJAX add pattern:', form.action);
        }
    });

    // AJAX delete logic for categories, subcategory1, subcategory2, color
    document.body.addEventListener('click', function(e) {
        const btn = e.target.closest('.ajax-delete-btn');
        if (btn) {
            e.preventDefault();
            const id = btn.dataset.id;
            const type = btn.dataset.type;
            let url = '';
            if (type === 'category') url = `/product/ajax/delete-category/${id}/`;
            if (type === 'subcategory1') url = `/product/ajax/delete-subcategory1/${id}/`;
            if (type === 'subcategory2') url = `/product/ajax/delete-subcategory2/${id}/`;
            if (type === 'color') url = `/product/ajax/delete-color/${id}/`;
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrftoken
                }
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    // Remove the item from the DOM or reload
                    location.reload();
                } else {
                    alert(data.error || 'Delete failed');
                }
            })
            .catch(() => {
                alert('Network or server error.');
            });
        }
    });

    // In-place AJAX edit logic for categories, subcategory1, subcategory2, color
    document.body.addEventListener('click', function(e) {
        const btn = e.target.closest('.ajax-edit-btn');
        if (btn) {
            e.preventDefault();
            const id = btn.dataset.id;
            const type = btn.dataset.type;
            const name = btn.dataset.name;
            // Find the span to replace
            const span = btn.closest('.list-group-item').querySelector('.fw-medium');
            if (!span) return;
            // Prevent multiple edits at once
            if (span.parentNode.querySelector('input.inplace-edit-input')) return;
            // Create input
            const input = document.createElement('input');
            input.type = 'text';
            input.value = name;
            input.className = 'form-control form-control-sm inplace-edit-input';
            input.style.width = 'auto';
            input.style.display = 'inline-block';
            input.style.maxWidth = '70%';
            input.setAttribute('data-id', id);
            input.setAttribute('data-type', type);
            input.setAttribute('data-original', name);
            span.style.display = 'none';
            span.parentNode.insertBefore(input, span);
            input.focus();
            input.select();
            // Handle save/cancel
            function finishEdit(success, newName) {
                if (success && newName) {
                    span.textContent = newName;
                    btn.dataset.name = newName;
                }
                span.style.display = '';
                input.remove();
            }
            input.addEventListener('keydown', function(ev) {
                if (ev.key === 'Enter') {
                    ev.preventDefault();
                    saveEdit();
                } else if (ev.key === 'Escape') {
                    finishEdit(false);
                }
            });
            input.addEventListener('blur', function() {
                saveEdit();
            });
            function saveEdit() {
                const newName = input.value.trim();
                if (newName === input.getAttribute('data-original')) {
                    finishEdit(false);
                    return;
                }
                let url = '';
                let data = new FormData();
                if (type === 'category') { url = `/product/ajax/update-category/${id}/`; data.append('product_category', newName); }
                if (type === 'subcategory1') { url = `/product/ajax/update-subcategory1/${id}/`; data.append('product_sub_category', newName); }
                if (type === 'subcategory2') { url = `/product/ajax/update-subcategory2/${id}/`; data.append('product_sub_category2', newName); }
                if (type === 'color') { url = `/product/ajax/update-color/${id}/`; data.append('color_name', newName); }
                fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrftoken
                    },
                    body: data
                })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        finishEdit(true, data.name);
                    } else {
                        // Show error and revert
                        finishEdit(false);
                        alert(data.errors ? Object.values(data.errors).flat().join(' ') : 'Update failed.');
                    }
                })
                .catch(() => {
                    finishEdit(false);
                    alert('Network or server error.');
                });
            }
        }
    });

    // Attach direct submit event listeners to all add forms when shown
    function attachDirectSubmitListenerFor(selector, logLabel) {
        const form = document.querySelector(selector);
        if (form && !form._directSubmitAttached) {
            form.addEventListener('submit', function(e) {
                console.log(`Direct submit event detected on ${logLabel} form:`, form);
            });
            form._directSubmitAttached = true;
        }
    }
    // When any add form is shown, attach the listener
    document.body.addEventListener('click', function(e) {
        // Add Category
        if (e.target && e.target.dataset && e.target.dataset.target === 'add-category-form') {
            setTimeout(() => attachDirectSubmitListenerFor('form[action*="ajax/add-category"]', 'Add Category'), 100);
        }
        // Add Subcategory1
        if (e.target && e.target.dataset && e.target.dataset.target && e.target.dataset.target.startsWith('add-subcategory1-form-')) {
            setTimeout(() => attachDirectSubmitListenerFor('form[action*="ajax/add-subcategory1"]', 'Add Subcategory1'), 100);
        }
        // Add Subcategory2
        if (e.target && e.target.dataset && e.target.dataset.target && e.target.dataset.target.startsWith('add-subcategory2-form-')) {
            setTimeout(() => attachDirectSubmitListenerFor('form[action*="ajax/add-subcategory2"]', 'Add Subcategory2'), 100);
        }
        // Add Color
        if (e.target && e.target.dataset && e.target.dataset.target && e.target.dataset.target.startsWith('add-color-form-')) {
            setTimeout(() => attachDirectSubmitListenerFor('form[action*="ajax/add-color"]', 'Add Color'), 100);
        }
        // Fallback: manually trigger submit for all add buttons
        if (e.target && e.target.id && e.target.id.startsWith('add-category-submit-btn')) {
            const parentForm = e.target.closest('form');
            if (parentForm) parentForm.requestSubmit();
        }
        if (e.target && e.target.id && e.target.id.startsWith('add-subcategory1-submit-btn')) {
            const parentForm = e.target.closest('form');
            if (parentForm) parentForm.requestSubmit();
        }
        if (e.target && e.target.id && e.target.id.startsWith('add-subcategory2-submit-btn')) {
            const parentForm = e.target.closest('form');
            if (parentForm) parentForm.requestSubmit();
        }
        if (e.target && e.target.id && e.target.id.startsWith('add-color-submit-btn')) {
            const parentForm = e.target.closest('form');
            if (parentForm) parentForm.requestSubmit();
        }
    });
});
