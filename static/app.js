// Use relative URL so it works regardless of hostname/IP
const API_BASE_URL = '/api';

// DOM Elements
const zoneName = document.getElementById('zoneName');
const recordCount = document.getElementById('recordCount');
const recordsTableBody = document.getElementById('recordsTableBody');
const loadingIndicator = document.getElementById('loadingIndicator');
const errorMessage = document.getElementById('errorMessage');
const addRecordForm = document.getElementById('addRecordForm');
const refreshBtn = document.getElementById('refreshBtn');
const editModal = document.getElementById('editModal');
const editRecordForm = document.getElementById('editRecordForm');
const cancelEditBtn = document.getElementById('cancelEditBtn');
const addModal = document.getElementById('addModal');
const addRecordBtn = document.getElementById('addRecordBtn');
const cancelAddBtn = document.getElementById('cancelAddBtn');
const searchInput = document.getElementById('searchInput');
const resultsCount = document.getElementById('resultsCount');
const typeFilters = document.getElementById('typeFilters');
const selectAllBtn = document.getElementById('selectAllBtn');
const deselectAllBtn = document.getElementById('deselectAllBtn');
const darkModeToggle = document.getElementById('darkModeToggle');
const moonIcon = document.getElementById('moonIcon');
const sunIcon = document.getElementById('sunIcon');
const settingsBtn = document.getElementById('settingsBtn');

// Store all records and selected types
let allRecords = [];
let selectedTypes = new Set();

// Check configuration status
async function checkConfigStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/config/status`);
        const data = await response.json();
        
        if (!data.configured) {
            // Redirect to settings page if not configured
            window.location.href = '/settings.html';
            return false;
        }
        return true;
    } catch (error) {
        console.error('Failed to check config status:', error);
        return false;
    }
}

// Dark Mode
function initDarkMode() {
    // Check localStorage first, default to light theme if not set
    const savedTheme = localStorage.getItem('theme');
    
    if (savedTheme === 'dark') {
        enableDarkMode();
    }
    // Default to light theme (do nothing)
}

function toggleDarkMode() {
    if (document.body.classList.contains('dark-mode')) {
        disableDarkMode();
    } else {
        enableDarkMode();
    }
}

function enableDarkMode() {
    document.body.classList.add('dark-mode');
    localStorage.setItem('theme', 'dark');
    moonIcon.style.display = 'none';
    sunIcon.style.display = 'block';
}

function disableDarkMode() {
    document.body.classList.remove('dark-mode');
    localStorage.setItem('theme', 'light');
    moonIcon.style.display = 'block';
    sunIcon.style.display = 'none';
}

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    initDarkMode();
    
    // Always attach settings button listener first, so it works even in SETUP MODE
    if (settingsBtn) {
        settingsBtn.addEventListener('click', () => window.location.href = '/settings.html');
    }
    
    // Always attach dark mode toggle
    if (darkModeToggle) {
        darkModeToggle.addEventListener('click', toggleDarkMode);
    }
    
    // Check if Azure credentials are configured
    const isConfigured = await checkConfigStatus();
    if (!isConfigured) {
        return; // Will be redirected to settings page
    }
    
    // Only load records if configured
    loadRecords();
    
    // Event listeners for record management (only needed when configured)
    addRecordForm.addEventListener('submit', handleAddRecord);
    editRecordForm.addEventListener('submit', handleEditRecord);
    refreshBtn.addEventListener('click', loadRecords);
    addRecordBtn.addEventListener('click', showAddModal);
    cancelEditBtn.addEventListener('click', hideEditModal);
    cancelAddBtn.addEventListener('click', hideAddModal);
    selectAllBtn.addEventListener('click', selectAllFilters);
    deselectAllBtn.addEventListener('click', deselectAllFilters);
    searchInput.addEventListener('input', applyFilters);
    
    // Close buttons for modals
    document.querySelectorAll('.close').forEach(closeBtn => {
        closeBtn.addEventListener('click', function() {
            const modal = this.closest('.modal');
            if (modal) {
                modal.classList.remove('active');
            }
        });
    });
    
    // Close modals when clicking backdrop
    document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
        backdrop.addEventListener('click', function() {
            const modal = this.closest('.modal');
            if (modal) {
                modal.classList.remove('active');
            }
        });
    });
});

// Load all DNS records
async function loadRecords() {
    try {
        showLoading(true);
        hideError();
        
        const response = await fetch(`${API_BASE_URL}/records`);
        const data = await response.json();
        
        if (!response.ok) {
            console.error('Error response:', data);
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }
        
        zoneName.textContent = data.zone;
        allRecords = data.records;
        
        // Build filter buttons from record types
        buildTypeFilters();
        
        // Apply filters
        applyFilters();
        
        showLoading(false);
    } catch (error) {
        console.error('Failed to load records:', error);
        showError(`Failed to load records: ${error.message}`);
        showLoading(false);
    }
}

// Display records in table
function displayRecords(records) {
    recordsTableBody.innerHTML = '';
    
    if (records.length === 0) {
        recordsTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 3rem; color: var(--color-slate-500);">No records found</td></tr>';
        return;
    }
    
    records.forEach((record, index) => {
        const row = document.createElement('tr');
        
        // Check if this is a protected record
        const isProtectedRecord = (record.name === '@' && (record.type === 'NS' || record.type === 'SOA'));
        
        const editDisabled = isProtectedRecord ? 'btn-disabled' : '';
        const editTitle = isProtectedRecord ? 'title="Root NS and SOA records cannot be edited"' : '';
        const deleteDisabled = isProtectedRecord ? 'btn-disabled' : '';
        const deleteTitle = isProtectedRecord ? 'title="Root NS and SOA records cannot be deleted"' : '';
        
        const valuesHtml = record.values.map(val => escapeHtml(val)).join('<br>');
        
        row.innerHTML = `
            <td>
                <div class="record-name">${escapeHtml(record.name)}</div>
                <div class="record-fqdn">${escapeHtml(record.fqdn)}</div>
            </td>
            <td>
                <span class="type-badge type-badge-${escapeHtml(record.type)}">${escapeHtml(record.type)}</span>
            </td>
            <td class="tabular-nums">${record.ttl}s</td>
            <td class="record-values">${valuesHtml}</td>
            <td class="col-actions">
                <div class="actions-group">
                    <button class="btn btn-action btn-action-edit ${editDisabled}" ${editTitle} ${isProtectedRecord ? 'disabled' : ''} 
                            onclick="editRecord('${escapeHtml(record.name)}', '${escapeHtml(record.type)}', ${record.ttl}, ${JSON.stringify(record.values).replace(/"/g, '&quot;')}, ${record.id})">
                        <svg class="btn-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                        </svg>
                        Edit
                    </button>
                    <button class="btn btn-action btn-action-delete ${deleteDisabled}" ${deleteTitle} ${isProtectedRecord ? 'disabled' : ''}
                            onclick="deleteRecord('${escapeHtml(record.name)}', '${escapeHtml(record.type)}', ${record.id})">
                        <svg class="btn-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                        </svg>
                        Delete
                    </button>
                </div>
            </td>
        `;
        
        recordsTableBody.appendChild(row);
    });
}

// Build dynamic type filter buttons
function buildTypeFilters() {
    const types = [...new Set(allRecords.map(r => r.type))].sort();
    typeFilters.innerHTML = '';
    
    types.forEach(type => {
        const button = document.createElement('button');
        button.className = 'filter-chip filter-chip-active';
        button.dataset.type = type;
        button.innerHTML = `<span class="type-badge type-badge-${type}">${type}</span>`;
        
        button.addEventListener('click', () => {
            if (selectedTypes.has(type)) {
                selectedTypes.delete(type);
                button.classList.remove('filter-chip-active');
            } else {
                selectedTypes.add(type);
                button.classList.add('filter-chip-active');
            }
            applyFilters();
        });
        
        typeFilters.appendChild(button);
        selectedTypes.add(type); // Start with all types selected
    });
}

// Add new record
async function handleAddRecord(e) {
    e.preventDefault();
    
    const name = document.getElementById('recordName').value.trim();
    const type = document.getElementById('recordType').value;
    const ttl = parseInt(document.getElementById('recordTTL').value);
    const valuesText = document.getElementById('recordValues').value.trim();
    
    // Parse values (one per line)
    const values = valuesText.split('\n').map(v => v.trim()).filter(v => v.length > 0);
    
    if (values.length === 0) {
        showError('Please enter at least one value');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/records`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ name, type, ttl, values }),
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to create record');
        }
        
        showSuccess('Record created successfully!');
        addRecordForm.reset();
        hideAddModal();
        loadRecords();
    } catch (error) {
        showError(`Failed to create record: ${error.message}`);
    }
}

// Edit record - show modal
function editRecord(name, type, ttl, values, id) {
    document.getElementById('editRecordName').value = name;
    document.getElementById('editRecordType').value = type;
    document.getElementById('editRecordId').value = id;
    document.getElementById('editRecordNameDisplay').value = name;
    document.getElementById('editRecordTypeDisplay').value = type;
    document.getElementById('editRecordTTL').value = ttl;
    document.getElementById('editRecordValues').value = values.join('\n');
    
    editModal.classList.add('active');
}

// Handle edit form submission
async function handleEditRecord(e) {
    e.preventDefault();
    
    const name = document.getElementById('editRecordName').value;
    const type = document.getElementById('editRecordType').value;
    const id = document.getElementById('editRecordId').value;
    const ttl = parseInt(document.getElementById('editRecordTTL').value);
    const valuesText = document.getElementById('editRecordValues').value.trim();
    
    const values = valuesText.split('\n').map(v => v.trim()).filter(v => v.length > 0);
    
    if (values.length === 0) {
        showError('Please enter at least one value');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/records/${type}/${name}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ ttl, values, id }),
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to update record');
        }
        
        showSuccess('Record updated successfully!');
        hideEditModal();
        loadRecords();
    } catch (error) {
        showError(`Failed to update record: ${error.message}`);
    }
}

// Delete record
async function deleteRecord(name, type, id) {
    if (!confirm(`Are you sure you want to delete the ${type} record "${name}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/records/${type}/${name}?id=${id}`, {
            method: 'DELETE',
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to delete record');
        }
        
        showSuccess('Record deleted successfully!');
        loadRecords();
    } catch (error) {
        showError(`Failed to delete record: ${error.message}`);
    }
}

// Modal functions
function hideEditModal() {
    editModal.classList.remove('active');
}

function showAddModal() {
    addModal.classList.add('active');
}

function hideAddModal() {
    addModal.classList.remove('active');
}

// UI Helper functions
function showLoading(show) {
    loadingIndicator.style.display = show ? 'block' : 'none';
}

function showError(message) {
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';
    setTimeout(() => {
        errorMessage.style.display = 'none';
    }, 5000);
}

function hideError() {
    errorMessage.style.display = 'none';
}

function showSuccess(message) {
    // Create temporary success message
    const successDiv = document.createElement('div');
    successDiv.className = 'success';
    successDiv.textContent = message;
    document.querySelector('.container').insertBefore(successDiv, document.querySelector('.main-content'));
    
    setTimeout(() => {
        successDiv.remove();
    }, 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Filter functions
function selectAllFilters() {
    document.querySelectorAll('.filter-chip').forEach(chip => {
        chip.classList.add('filter-chip-active');
        const type = chip.dataset.type;
        if (type) selectedTypes.add(type);
    });
    applyFilters();
}

function deselectAllFilters() {
    document.querySelectorAll('.filter-chip').forEach(chip => {
        chip.classList.remove('filter-chip-active');
        const type = chip.dataset.type;
        if (type) selectedTypes.delete(type);
    });
    applyFilters();
}

function applyFilters() {
    const searchTerm = searchInput.value.toLowerCase().trim();
    
    // Filter by type and search
    const filteredRecords = allRecords.filter(record => {
        // Check type filter
        if (!selectedTypes.has(record.type)) {
            return false;
        }
        
        // Check search term
        if (searchTerm) {
            const searchableText = [
                record.name,
                record.type,
                record.fqdn,
                record.ttl.toString(),
                ...record.values
            ].join(' ').toLowerCase();
            
            if (!searchableText.includes(searchTerm)) {
                return false;
            }
        }
        
        return true;
    });
    
    // Update counts
    recordCount.textContent = allRecords.length;
    resultsCount.textContent = filteredRecords.length;
    
    // Display filtered records
    displayRecords(filteredRecords);
}
