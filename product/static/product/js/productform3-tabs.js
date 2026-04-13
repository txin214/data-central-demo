function showTab(tabId) {
    // Hide all tab content
    const tabs = document.querySelectorAll('.tab-content');
    tabs.forEach(tab => tab.classList.remove('active'));

    // Show the selected tab
    const activeTab = document.getElementById(tabId);
    activeTab.classList.add('active');

    // Update tab button styles
    const tabButtons = document.querySelectorAll('.TabTable td');
    tabButtons.forEach(button => button.classList.remove('CurrentTab'));
    document.querySelector(`.TabTable td[onclick="showTab('${tabId}')"]`).classList.add('CurrentTab');
}

document.addEventListener('DOMContentLoaded', function () {
    const categorySelect = document.getElementById('id_category');
    const subCategory1Select = document.getElementById('id_sub_category1');
    const subCategory2Select = document.getElementById('id_sub_category2');

    categorySelect.addEventListener('change', function () {
        const categoryId = this.value;

        // Fetch subcategories based on the selected category
        fetch(`/product/ajax/load-subcategories/?category=${categoryId}`)
            .then(response => response.json())
            .then(data => {
                subCategory1Select.innerHTML = '<option value="">Select Subcategory Level 1</option>';
                subCategory2Select.innerHTML = '<option value="">Select Subcategory Level 2</option>';

                data.subcategories1.forEach(subcategory1 => {
                    const option = document.createElement('option');
                    option.value = subcategory1.id;
                    option.text = subcategory1.product_sub_category;
                    subCategory1Select.add(option);
                });

                subCategory1Select.disabled = false;
                subCategory2Select.disabled = true;
            });
    });

    subCategory1Select.addEventListener('change', function () {
        const subCategory1Id = this.value;

        // Fetch subcategories level 2 based on the selected subcategory1
        fetch(`/product/ajax/load-subcategories/?category=${categorySelect.value}&subcategory1=${subCategory1Id}`)
            .then(response => response.json())
            .then(data => {
                subCategory2Select.innerHTML = '<option value="">Select Subcategory Level 2</option>';

                data.subcategories2.forEach(subcategory2 => {
                    const option = document.createElement('option');
                    option.value = subcategory2.id;
                    option.text = subcategory2.product_sub_category2;
                    subCategory2Select.add(option);
                });

                subCategory2Select.disabled = false;
            });
    });
});

