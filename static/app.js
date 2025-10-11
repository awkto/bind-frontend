// Use relative URL so it works regardless of hostname/IP
const API_BASE_URL = '/api';

// DOM Elements
const zoneSelector = document.getElementById('zoneSelector');
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
const createZoneBtn = document.getElementById('createZoneBtn');
const createZoneModal = document.getElementById('createZoneModal');
const createZoneForm = document.getElementById('createZoneForm');
const cancelCreateZoneBtn = document.getElementById('cancelCreateZoneBtn');
const searchInput = document.getElementById('searchInput');
const resultsCount = document.getElementById('resultsCount');
const typeFilters = document.getElementById('typeFilters');
const selectAllBtn = document.getElementById('selectAllBtn');
const deselectAllBtn = document.getElementById('deselectAllBtn');
const darkModeToggle = document.getElementById('darkModeToggle');
const moonIcon = document.getElementById('moonIcon');
const sunIcon = document.getElementById('sunIcon');
const settingsBtn = document.getElementById('settingsBtn');
const manageServersBtn = document.getElementById('manageServersBtn');

// Store all records and selected types
let allRecords = [];
let selectedTypes = new Set();
let availableZones = [];
let currentZone = null;
let availableServers = [];
let currentServerId = null;

// Check configuration status
async function checkConfigStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/config/status`);
        const data = await response.json();
        
        if (!data.configured && !data.has_servers) {
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

// Load available zones
async function loadZones() {
    try {
        const response = await fetch(`${API_BASE_URL}/zones`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to load zones');
        }
        
        availableZones = data.zones || [];
        
        // Populate zone selector
        zoneSelector.innerHTML = '';
        if (availableZones.length === 0) {
            zoneSelector.innerHTML = '<option value="">No zones found</option>';
            return;
        }
        
        availableZones.forEach(zone => {
            const option = document.createElement('option');
            option.value = zone.name;
            option.textContent = zone.name;
            zoneSelector.appendChild(option);
        });
        
        // Load saved zone preference or select first zone
        const savedZone = localStorage.getItem('selectedZone');
        if (savedZone && availableZones.find(z => z.name === savedZone)) {
            currentZone = savedZone;
            zoneSelector.value = savedZone;
        } else if (availableZones.length > 0) {
            currentZone = availableZones[0].name;
            zoneSelector.value = currentZone;
        }
        
        // Load records for the selected zone
        if (currentZone) {
            await loadRecords();
        }
    } catch (error) {
        console.error('Failed to load zones:', error);
        showError(`Failed to load zones: ${error.message}`);
    }
}

// Handle zone selection change
function handleZoneChange() {
    currentZone = zoneSelector.value;
    if (currentZone) {
        localStorage.setItem('selectedZone', currentZone);
        loadRecords();
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
    
    // Always attach button listeners first, so they work even in SETUP MODE
    if (settingsBtn) {
        settingsBtn.addEventListener('click', () => window.location.href = '/settings.html');
    }
    
    if (manageServersBtn) {
        manageServersBtn.addEventListener('click', () => window.location.href = '/servers.html');
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
    
    // Load zones and records
    await loadZones();
    
    // Zone selector change listener
    if (zoneSelector) {
        zoneSelector.addEventListener('change', handleZoneChange);
    }
    
    // Event listeners for record management (only needed when configured)
    addRecordForm.addEventListener('submit', handleAddRecord);
    editRecordForm.addEventListener('submit', handleEditRecord);
    createZoneForm.addEventListener('submit', handleCreateZone);
    refreshBtn.addEventListener('click', loadRecords);
    addRecordBtn.addEventListener('click', showAddModal);
    createZoneBtn.addEventListener('click', showCreateZoneModal);
    cancelEditBtn.addEventListener('click', hideEditModal);
    cancelAddBtn.addEventListener('click', hideAddModal);
    cancelCreateZoneBtn.addEventListener('click', hideCreateZoneModal);
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
        if (!currentZone) {
            showError('Please select a zone');
            return;
        }
        
        showLoading(true);
        hideError();
        
        const response = await fetch(`${API_BASE_URL}/records?zone=${encodeURIComponent(currentZone)}`);
        const data = await response.json();
        
        if (!response.ok) {
            console.error('Error response:', data);
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }
        
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
    
    // Clear previous messages
    hideModalMessages('addModal');
    
    const name = document.getElementById('recordName').value.trim();
    const type = document.getElementById('recordType').value;
    const ttl = parseInt(document.getElementById('recordTTL').value);
    const valuesText = document.getElementById('recordValues').value.trim();
    
    // Parse values (one per line)
    const values = valuesText.split('\n').map(v => v.trim()).filter(v => v.length > 0);
    
    if (values.length === 0) {
        showModalError('addModal', 'Please enter at least one value');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/records`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ zone: currentZone, name, type, ttl, values }),
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to create record');
        }
        
        showModalSuccess('addModal', 'Record created successfully!');
        setTimeout(() => {
            addRecordForm.reset();
            hideAddModal();
            loadRecords();
        }, 1500);
    } catch (error) {
        showModalError('addModal', `Failed to create record: ${error.message}`);
    }
}

// Edit record - show modal
function editRecord(name, type, ttl, values, id) {
    hideModalMessages('editModal');
    
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
    
    // Clear previous messages
    hideModalMessages('editModal');
    
    const name = document.getElementById('editRecordName').value;
    const type = document.getElementById('editRecordType').value;
    const id = document.getElementById('editRecordId').value;
    const ttl = parseInt(document.getElementById('editRecordTTL').value);
    const valuesText = document.getElementById('editRecordValues').value.trim();
    
    const values = valuesText.split('\n').map(v => v.trim()).filter(v => v.length > 0);
    
    if (values.length === 0) {
        showModalError('editModal', 'Please enter at least one value');
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
        
        showModalSuccess('editModal', 'Record updated successfully!');
        setTimeout(() => {
            hideEditModal();
            loadRecords();
        }, 1500);
    } catch (error) {
        showModalError('editModal', `Failed to update record: ${error.message}`);
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
    // Update zone badge in the modal
    const zoneBadge = document.getElementById('addRecordZoneBadge');
    if (zoneBadge && currentZone) {
        zoneBadge.innerHTML = `
            <svg class="badge-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z"/>
            </svg>
            Zone: ${currentZone}
        `;
        zoneBadge.style.display = 'inline-flex';
    } else if (zoneBadge) {
        zoneBadge.style.display = 'none';
    }
    
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

// Modal-specific error/success functions
function showModalError(modalId, message) {
    const errorElement = document.getElementById(`${modalId}Error`);
    const successElement = document.getElementById(`${modalId}Success`);
    
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
        if (successElement) successElement.style.display = 'none';
        
        // Auto-hide after 10 seconds
        setTimeout(() => {
            errorElement.style.display = 'none';
        }, 10000);
    }
}

function showModalSuccess(modalId, message) {
    const errorElement = document.getElementById(`${modalId}Error`);
    const successElement = document.getElementById(`${modalId}Success`);
    
    if (successElement) {
        successElement.textContent = message;
        successElement.style.display = 'block';
        if (errorElement) errorElement.style.display = 'none';
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            successElement.style.display = 'none';
        }, 5000);
    }
}

function hideModalMessages(modalId) {
    const errorElement = document.getElementById(`${modalId}Error`);
    const successElement = document.getElementById(`${modalId}Success`);
    
    if (errorElement) errorElement.style.display = 'none';
    if (successElement) successElement.style.display = 'none';
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

// Create Zone Modal Functions
function showCreateZoneModal() {
    createZoneForm.reset();
    hideModalMessages('createZoneModal');
    createZoneModal.classList.add('active');
    
    // Set up auto-populate for admin email when zone name changes
    const zoneNameInput = document.getElementById('zoneName');
    const adminEmailInput = document.getElementById('adminEmail');
    const primaryNSInput = document.getElementById('primaryNS');
    const nsIpInput = document.getElementById('nsIpAddress');
    
    // Auto-populate admin email based on zone name
    const handleZoneNameChange = () => {
        const zoneName = zoneNameInput.value.trim();
        if (zoneName && !adminEmailInput.value) {
            adminEmailInput.value = `admin@${zoneName}`;
        }
    };
    
    // Remove any existing listeners
    zoneNameInput.removeEventListener('blur', handleZoneNameChange);
    // Add new listener
    zoneNameInput.addEventListener('blur', handleZoneNameChange);
    
    // Add helper to detect if NS is within zone
    const handleNSChange = () => {
        const zoneName = zoneNameInput.value.trim();
        const primaryNS = primaryNSInput.value.trim();
        
        if (zoneName && primaryNS && primaryNS.endsWith(`.${zoneName}`)) {
            // NS is within the zone - make IP required and enable field
            nsIpInput.setAttribute('required', 'required');
            nsIpInput.removeAttribute('disabled');
            nsIpInput.parentElement.querySelector('label').innerHTML = 'Nameserver IP Address *';
            nsIpInput.parentElement.querySelector('.form-help').innerHTML = 
                '<strong>Required for in-zone nameserver</strong> - Creates a glue record (A record) for the nameserver.';
            nsIpInput.parentElement.style.opacity = '1';
        } else if (zoneName && primaryNS) {
            // NS is external - disable IP field and clear value
            nsIpInput.removeAttribute('required');
            nsIpInput.setAttribute('disabled', 'disabled');
            nsIpInput.value = '';
            nsIpInput.parentElement.querySelector('label').innerHTML = 'Nameserver IP Address';
            nsIpInput.parentElement.querySelector('.form-help').innerHTML = 
                'Not applicable - nameserver is outside this zone (no glue record needed).';
            nsIpInput.parentElement.style.opacity = '0.5';
        } else {
            // Not enough info yet - keep field enabled but optional
            nsIpInput.removeAttribute('required');
            nsIpInput.removeAttribute('disabled');
            nsIpInput.parentElement.querySelector('label').innerHTML = 'Nameserver IP Address';
            nsIpInput.parentElement.querySelector('.form-help').innerHTML = 
                '<strong>Required if NS is within this zone</strong> (e.g., ns1.example.com for example.com zone). This creates a glue record (A record) for the nameserver.';
            nsIpInput.parentElement.style.opacity = '1';
        }
    };
    
    primaryNSInput.removeEventListener('blur', handleNSChange);
    primaryNSInput.addEventListener('blur', handleNSChange);
    primaryNSInput.removeEventListener('input', handleNSChange);
    primaryNSInput.addEventListener('input', handleNSChange);
    zoneNameInput.removeEventListener('blur', handleNSChange);
    zoneNameInput.addEventListener('blur', handleNSChange);
    zoneNameInput.removeEventListener('input', handleNSChange);
    zoneNameInput.addEventListener('input', handleNSChange);
}

function hideCreateZoneModal() {
    createZoneModal.classList.remove('active');
}

// Handle Create Zone
async function handleCreateZone(e) {
    e.preventDefault();
    
    // Clear previous messages
    hideModalMessages('createZoneModal');
    
    const zoneName = document.getElementById('zoneName').value.trim();
    const primaryNS = document.getElementById('primaryNS').value.trim();
    const adminEmail = document.getElementById('adminEmail').value.trim();
    const nsIpAddress = document.getElementById('nsIpAddress').value.trim();
    
    if (!zoneName || !primaryNS || !adminEmail) {
        showModalError('createZoneModal', 'Please fill in all required fields');
        return;
    }
    
    // Check if NS is within the zone and requires IP
    const nsIsInZone = primaryNS.endsWith(`.${zoneName}`) || primaryNS === zoneName;
    if (nsIsInZone && !nsIpAddress) {
        showModalError('createZoneModal', 'Nameserver IP address is required when the NS record is within this zone (glue record needed)');
        return;
    }
    
    // Validate IP address format if provided
    if (nsIpAddress) {
        const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
        if (!ipRegex.test(nsIpAddress)) {
            showModalError('createZoneModal', 'Invalid IP address format');
            return;
        }
        
        // Validate IP octets
        const octets = nsIpAddress.split('.');
        if (octets.some(octet => parseInt(octet) > 255 || parseInt(octet) < 0)) {
            showModalError('createZoneModal', 'Invalid IP address: octets must be between 0 and 255');
            return;
        }
    }
    
    try {
        showLoading(true);
        
        const requestBody = {
            zone_name: zoneName,
            primary_ns: primaryNS,
            admin_email: adminEmail
        };
        
        // Only include ns_ip_address if provided
        if (nsIpAddress) {
            requestBody.ns_ip_address = nsIpAddress;
        }
        
        const response = await fetch(`${API_BASE_URL}/zones`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody),
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Success!
            showModalSuccess('createZoneModal', `✅ Zone ${zoneName} created successfully! Refreshing zones...`);
            
            setTimeout(async () => {
                hideCreateZoneModal();
                await loadZones();
                
                // Select the newly created zone
                const zoneOption = Array.from(zoneSelector.options).find(opt => opt.value === zoneName);
                if (zoneOption) {
                    zoneSelector.value = zoneName;
                    await handleZoneChange();
                }
            }, 2000);
        } else {
            showModalError('createZoneModal', data.error || 'Failed to create zone');
        }
    } catch (error) {
        showError(`Failed to create zone: ${error.message}`);
    } finally {
        showLoading(false);
    }
}
