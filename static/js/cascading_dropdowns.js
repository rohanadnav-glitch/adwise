async function populateDropdown(url, targetSelect, defaultOptionText, dataKey) {
    targetSelect.innerHTML = `<option value="">Loading...</option>`;
    targetSelect.disabled = true;

    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error('Network error');
        
        const data = await response.json();
        targetSelect.innerHTML = `<option value="">${defaultOptionText}</option>`;

        data[dataKey].forEach(item => {
            const option = document.createElement('option');
            option.value = item.id;
            option.textContent = item.name;
            targetSelect.appendChild(option);
        });

        targetSelect.disabled = false;
    } catch (error) {
        console.error('Fetch error:', error);
        targetSelect.innerHTML = `<option value="">Error loading items</option>`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const stateSelect = document.getElementById('id_state');
    const districtSelect = document.getElementById('id_district');
    const citySelect = document.getElementById('id_city');

    const categorySelect = document.getElementById('id_category');
    const subcategorySelect = document.getElementById('id_subcategory');

    // 1. State -> District
    if (stateSelect && districtSelect) {
        stateSelect.addEventListener('change', (e) => {
            const stateId = e.target.value;
            if (citySelect) {
                citySelect.innerHTML = '<option value="">Select City</option>';
                citySelect.disabled = true;
            }
            if (stateId) {
                populateDropdown(
                    `/locations/api/districts/?state_id=${stateId}`,
                    districtSelect,
                    'Select District',
                    'districts'
                );
            } else {
                districtSelect.innerHTML = '<option value="">Select District</option>';
                districtSelect.disabled = true;
            }
        });
    }

    // 2. District -> City
    if (districtSelect && citySelect) {
        districtSelect.addEventListener('change', (e) => {
            const districtId = e.target.value;
            if (districtId) {
                populateDropdown(
                    `/locations/api/cities/?district_id=${districtId}`,
                    citySelect,
                    'Select City',
                    'cities'
                );
            } else {
                citySelect.innerHTML = '<option value="">Select City</option>';
                citySelect.disabled = true;
            }
        });
    }

    // 3. Category -> SubCategory
    if (categorySelect && subcategorySelect) {
        categorySelect.addEventListener('change', (e) => {
            const categoryId = e.target.value;
            if (categoryId) {
                populateDropdown(
                    `/categories/api/subcategories/?category_id=${categoryId}`,
                    subcategorySelect,
                    'Select SubCategory',
                    'subcategories'
                );
            } else {
                subcategorySelect.innerHTML = '<option value="">Select SubCategory</option>';
                subcategorySelect.disabled = true;
            }
        });
    }
});