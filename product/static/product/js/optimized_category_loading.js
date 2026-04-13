/**
 * Optimized Category Loading JavaScript
 * Loads all categories, subcategories, and manufacturers in a single request
 * and caches the data client-side for better performance
 */

class OptimizedCategoryLoader {
    constructor() {
        this.categoryData = null;
        this.isLoading = false;
        this.loadPromise = null;
    }

    /**
     * Load all category data in a single request
     */
    async loadAllCategories() {
        if (this.categoryData) {
            return this.categoryData;
        }

        if (this.isLoading) {
            return this.loadPromise;
        }

        this.isLoading = true;
        this.loadPromise = fetch('/product/ajax/all-categories/')
            .then(response => response.json())
            .then(data => {
                this.categoryData = data;
                this.isLoading = false;
                return data;
            })
            .catch(error => {
                console.error('Error loading categories:', error);
                this.isLoading = false;
                throw error;
            });

        return this.loadPromise;
    }

    /**
     * Populate category dropdown
     */
    populateCategoryDropdown(selectElement) {
        if (!this.categoryData) return;

        selectElement.innerHTML = '<option value="">Category</option>';
        this.categoryData.categories.forEach(category => {
            const option = document.createElement('option');
            option.value = category.id;
            option.textContent = category.name;
            selectElement.appendChild(option);
        });
    }

    /**
     * Populate subcategory1 dropdown based on selected category
     */
    populateSubcategory1Dropdown(selectElement, categoryId) {
        if (!this.categoryData || !categoryId) {
            selectElement.innerHTML = '<option value="">Subcategory 1</option>';
            selectElement.disabled = true;
            return;
        }

        const subcategories = this.categoryData.subcategories1_by_category[categoryId] || [];
        selectElement.innerHTML = '<option value="">Subcategory 1</option>';
        subcategories.forEach(subcat => {
            const option = document.createElement('option');
            option.value = subcat.id;
            option.textContent = subcat.name;
            selectElement.appendChild(option);
        });
        selectElement.disabled = false;
    }

    /**
     * Populate subcategory2 dropdown based on selected subcategory1
     */
    populateSubcategory2Dropdown(selectElement, subcat1Id) {
        if (!this.categoryData || !subcat1Id) {
            selectElement.innerHTML = '<option value="">Subcategory 2</option>';
            selectElement.disabled = true;
            return;
        }

        const subcategories = this.categoryData.subcategories2_by_subcat1[subcat1Id] || [];
        selectElement.innerHTML = '<option value="">Subcategory 2</option>';
        subcategories.forEach(subcat => {
            const option = document.createElement('option');
            option.value = subcat.id;
            option.textContent = subcat.name;
            selectElement.appendChild(option);
        });
        selectElement.disabled = false;
    }

    /**
     * Populate manufacturer dropdown
     */
    populateManufacturerDropdown(selectElement) {
        if (!this.categoryData) return;

        selectElement.innerHTML = '<option value="">Manufacturer</option>';
        this.categoryData.manufacturers.forEach(manufacturer => {
            const option = document.createElement('option');
            option.value = manufacturer.id;
            option.textContent = manufacturer.name;
            selectElement.appendChild(option);
        });
    }

    /**
     * Initialize all dropdowns with optimized loading
     */
    async initializeDropdowns(options = {}) {
        const {
            categorySelect,
            subcategory1Select,
            subcategory2Select,
            manufacturerSelect,
            onCategoryChange,
            onSubcategory1Change,
            onSubcategory2Change,
            onManufacturerChange
        } = options;

        try {
            await this.loadAllCategories();

            // Populate initial dropdowns
            if (categorySelect) {
                this.populateCategoryDropdown(categorySelect);
            }
            if (manufacturerSelect) {
                this.populateManufacturerDropdown(manufacturerSelect);
            }

            // Set up event listeners
            if (categorySelect) {
                categorySelect.addEventListener('change', (e) => {
                    const categoryId = e.target.value;
                    if (subcategory1Select) {
                        this.populateSubcategory1Dropdown(subcategory1Select, categoryId);
                    }
                    if (subcategory2Select) {
                        this.populateSubcategory2Dropdown(subcategory2Select, '');
                    }
                    if (onCategoryChange) {
                        onCategoryChange(categoryId);
                    }
                });
            }

            if (subcategory1Select) {
                subcategory1Select.addEventListener('change', (e) => {
                    const subcat1Id = e.target.value;
                    if (subcategory2Select) {
                        this.populateSubcategory2Dropdown(subcategory2Select, subcat1Id);
                    }
                    if (onSubcategory1Change) {
                        onSubcategory1Change(subcat1Id);
                    }
                });
            }

            if (subcategory2Select && onSubcategory2Change) {
                subcategory2Select.addEventListener('change', (e) => {
                    onSubcategory2Change(e.target.value);
                });
            }

            if (manufacturerSelect && onManufacturerChange) {
                manufacturerSelect.addEventListener('change', (e) => {
                    onManufacturerChange(e.target.value);
                });
            }

        } catch (error) {
            console.error('Failed to initialize dropdowns:', error);
        }
    }

    /**
     * Clear cached data (useful for testing or when data changes)
     */
    clearCache() {
        this.categoryData = null;
        this.isLoading = false;
        this.loadPromise = null;
    }
}

// Global instance
window.optimizedCategoryLoader = new OptimizedCategoryLoader();

// Auto-initialize if DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on a page that needs category dropdowns
    const categorySelect = document.getElementById('categoryDropdown') || 
                          document.getElementById('category') ||
                          document.getElementById('id_category');
    
    if (categorySelect) {
        const subcategory1Select = document.getElementById('subcat1Dropdown') || 
                                  document.getElementById('sub_category1') ||
                                  document.getElementById('id_sub_category1');
        
        const subcategory2Select = document.getElementById('subcat2Dropdown') || 
                                  document.getElementById('sub_category2') ||
                                  document.getElementById('id_sub_category2');
        
        const manufacturerSelect = document.getElementById('manufacturerDropdown') || 
                                 document.getElementById('manufacturer') ||
                                 document.getElementById('id_manufacturer');

        window.optimizedCategoryLoader.initializeDropdowns({
            categorySelect,
            subcategory1Select,
            subcategory2Select,
            manufacturerSelect,
            onCategoryChange: (categoryId) => {
                // Trigger product filtering if function exists
                if (typeof fetchProducts === 'function') {
                    fetchProducts();
                }
                if (typeof updateBreadcrumb === 'function') {
                    updateBreadcrumb();
                }
            },
            onSubcategory1Change: (subcat1Id) => {
                if (typeof fetchProducts === 'function') {
                    fetchProducts();
                }
                if (typeof updateBreadcrumb === 'function') {
                    updateBreadcrumb();
                }
            },
            onSubcategory2Change: (subcat2Id) => {
                if (typeof fetchProducts === 'function') {
                    fetchProducts();
                }
                if (typeof updateBreadcrumb === 'function') {
                    updateBreadcrumb();
                }
            },
            onManufacturerChange: (manufacturerId) => {
                if (typeof fetchProducts === 'function') {
                    fetchProducts();
                }
            }
        });
    }
}); 