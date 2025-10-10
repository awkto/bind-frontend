// Use relative URL so it works regardless of hostname/IP
const API_BASE_URL = '/api';

// DOM Elements
const settingsForm = document.getElementById('settingsForm');
const testConnectionBtn = document.getElementById('testConnectionBtn');
const loadingMessage = document.getElementById('loadingMessage');
const successMessage = document.getElementById('successMessage');
const errorMessage = document.getElementById('errorMessage');

const bindHostInput = document.getElementById('bindHost');
const bindPortInput = document.getElementById('bindPort');
const bindUserInput = document.getElementById('bindUser');
const bindSshKeyInput = document.getElementById('bindSshKey');
const bindPasswordInput = document.getElementById('bindPassword');
const dnsZoneInput = document.getElementById('dnsZone');
const zoneFilePathInput = document.getElementById('zoneFilePath');

const toggleSecretBtn = document.getElementById('toggleSecretBtn');
const eyeIcon = document.getElementById('eyeIcon');
const eyeOffIcon = document.getElementById('eyeOffIcon');

// Track if this is a first-time setup
let isSetupMode = false;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadCurrentConfig();
    
    settingsForm.addEventListener('submit', handleSaveConfig);
    testConnectionBtn.addEventListener('click', handleTestConnection);
    toggleSecretBtn.addEventListener('click', toggleSecretVisibility);
});

// Toggle password visibility
function toggleSecretVisibility() {
    if (bindPasswordInput.type === 'password') {
        bindPasswordInput.type = 'text';
        eyeIcon.style.display = 'none';
        eyeOffIcon.style.display = 'block';
    } else {
        bindPasswordInput.type = 'password';
        eyeIcon.style.display = 'block';
        eyeOffIcon.style.display = 'none';
    }
}

// Load current configuration
async function loadCurrentConfig() {
    try {
        showLoading(true);
        hideMessages();
        
        const response = await fetch(`${API_BASE_URL}/config`);
        const data = await response.json();
        
        if (response.ok) {
            // Check if any configuration is missing (SETUP MODE)
            const hasAnyConfig = data.bind_host || data.dns_zone;
            
            isSetupMode = !hasAnyConfig;
            
            // Update UI based on setup mode
            const backNavigation = document.getElementById('backNavigation');
            const settingsDescription = document.getElementById('settingsDescription');
            
            if (isSetupMode) {
                // Hide back button in setup mode
                if (backNavigation) {
                    backNavigation.style.display = 'none';
                }
                // Update description for first-time setup
                if (settingsDescription) {
                    settingsDescription.innerHTML = '🚀 <strong>Welcome!</strong> Please configure your BIND DNS server connection to get started.';
                }
            } else {
                // Show back button when configuration exists
                if (backNavigation) {
                    backNavigation.style.display = 'block';
                }
            }
            
            // Populate form with current config
            bindHostInput.value = data.bind_host || '';
            bindPortInput.value = data.bind_port || '22';
            bindUserInput.value = data.bind_user || '';
            bindSshKeyInput.value = data.bind_ssh_key || '';
            dnsZoneInput.value = data.dns_zone || '';
            zoneFilePathInput.value = data.zone_file_path || '';
            
            // Don't show the password value for security
            bindPasswordInput.value = '';
            bindPasswordInput.placeholder = data.has_credentials ? 'Leave empty to keep existing' : 'SSH password (if not using key)';
        }
        
        showLoading(false);
    } catch (error) {
        showLoading(false);
        showError(`Failed to load configuration: ${error.message}`);
    }
}

// Test connection
async function handleTestConnection(e) {
    e.preventDefault();
    
    try {
        hideMessages();
        testConnectionBtn.disabled = true;
        testConnectionBtn.innerHTML = '<span>Testing...</span>';
        
        const config = getFormData();
        
        // Validate required fields
        if (!validateConfig(config)) {
            showError('Please fill in all required fields (Host, User, DNS Zone, Zone File Path, and either SSH Key or Password)');
            return;
        }
        
        const response = await fetch(`${API_BASE_URL}/config/test`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config),
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess(`✅ ${data.message}`);
        } else {
            showError(data.error || 'Connection test failed');
        }
    } catch (error) {
        showError(`Test failed: ${error.message}`);
    } finally {
        testConnectionBtn.disabled = false;
        testConnectionBtn.innerHTML = `
            <svg class="btn-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            Test Connection
        `;
    }
}

// Save configuration
async function handleSaveConfig(e) {
    e.preventDefault();
    
    try {
        hideMessages();
        
        const config = getFormData();
        
        // Validate required fields
        if (!validateConfig(config)) {
            showError('Please fill in all required fields (Host, User, DNS Zone, Zone File Path, and either SSH Key or Password)');
            return;
        }
        
        const response = await fetch(`${API_BASE_URL}/config`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config),
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess(`✅ Configuration saved successfully! DNS Zone: ${data.zone}`);
            
            // Redirect to main page after 2 seconds
            setTimeout(() => {
                window.location.href = '/';
            }, 2000);
        } else {
            showError(data.error || 'Failed to save configuration');
        }
    } catch (error) {
        showError(`Save failed: ${error.message}`);
    }
}

// Helper functions
function getFormData() {
    return {
        bind_host: bindHostInput.value.trim(),
        bind_port: bindPortInput.value.trim() || '22',
        bind_user: bindUserInput.value.trim(),
        bind_ssh_key: bindSshKeyInput.value.trim(),
        bind_password: bindPasswordInput.value.trim(),
        dns_zone: dnsZoneInput.value.trim(),
        zone_file_path: zoneFilePathInput.value.trim()
    };
}

function validateConfig(config) {
    // Required fields
    if (!config.bind_host || !config.bind_user || !config.dns_zone || !config.zone_file_path) {
        return false;
    }
    // Must have either SSH key or password
    if (!config.bind_ssh_key && !config.bind_password) {
        return false;
    }
    return true;
}

function showLoading(show) {
    loadingMessage.style.display = show ? 'block' : 'none';
}

function showSuccess(message) {
    successMessage.textContent = message;
    successMessage.style.display = 'block';
    errorMessage.style.display = 'none';
    
    // Auto-hide after 10 seconds
    setTimeout(() => {
        successMessage.style.display = 'none';
    }, 10000);
}

function showError(message) {
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';
    successMessage.style.display = 'none';
}

function hideMessages() {
    successMessage.style.display = 'none';
    errorMessage.style.display = 'none';
}
