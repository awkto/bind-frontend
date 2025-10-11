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
const bindConfigPathInput = document.getElementById('bindConfigPath');
const installBindCheckbox = document.getElementById('installBind');

const toggleSecretBtn = document.getElementById('toggleSecretBtn');
const eyeIcon = document.getElementById('eyeIcon');
const eyeOffIcon = document.getElementById('eyeOffIcon');

const installModal = document.getElementById('installModal');
const installSteps = document.getElementById('installSteps');
const closeInstallModalBtn = document.getElementById('closeInstallModal');

// Track if this is a first-time setup
let isSetupMode = false;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadCurrentConfig();
    
    settingsForm.addEventListener('submit', handleSaveConfig);
    testConnectionBtn.addEventListener('click', handleTestConnection);
    toggleSecretBtn.addEventListener('click', toggleSecretVisibility);
    if (closeInstallModalBtn) {
        closeInstallModalBtn.addEventListener('click', closeInstallModal);
    }
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
            const hasAnyConfig = data.bind_host;
            
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
                    settingsDescription.innerHTML = '🚀 <strong>Welcome!</strong> Please configure your BIND DNS server connection to get started. Zones will be auto-discovered.';
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
            bindConfigPathInput.value = data.bind_config_path || '/etc/bind/named.conf';
            
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
            showError('Please fill in all required fields (Host, User, and either SSH Key or Password)');
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
            // Display success message with BIND installation status
            showSuccess(`✅ ${data.message}`);
            
            // If BIND is not installed, show a note about the install checkbox
            if (data.bindInstalled === false) {
                const installCheckboxContainer = document.querySelector('.install-bind-container');
                if (installCheckboxContainer) {
                    installCheckboxContainer.style.border = '2px solid #f39c12';
                    installCheckboxContainer.style.backgroundColor = '#fef5e7';
                    installCheckboxContainer.style.padding = '12px';
                    installCheckboxContainer.style.borderRadius = '8px';
                    installCheckboxContainer.style.marginTop = '10px';
                    
                    // Add a note if it doesn't exist
                    let note = installCheckboxContainer.querySelector('.install-note');
                    if (!note) {
                        note = document.createElement('div');
                        note.className = 'install-note';
                        note.style.fontSize = '13px';
                        note.style.color = '#856404';
                        note.style.marginTop = '8px';
                        note.innerHTML = '💡 Check the box above to install BIND when saving configuration.';
                        installCheckboxContainer.appendChild(note);
                    }
                    
                    // Scroll to the install checkbox
                    setTimeout(() => {
                        installCheckboxContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }, 500);
                }
            }
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
    
    // Check if user wants to install BIND first
    if (installBindCheckbox && installBindCheckbox.checked) {
        hideMessages();
        
        const installed = await installBind();
        
        if (!installed) {
            return; // Don't save config if installation failed
        }
        
        // Wait a moment for user to see completion
        await new Promise(resolve => setTimeout(resolve, 2000));
        closeInstallModal();
        
        // Uncheck the install checkbox so we don't try to install again on next save
        installBindCheckbox.checked = false;
    }
    
    // Now save the configuration
    try {
        hideMessages();
        
        const config = getFormData();
        
        // Validate required fields
        if (!validateConfig(config)) {
            showError('Please fill in all required fields (Host, User, and either SSH Key or Password)');
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
            // Show success message
            let message = '✅ Configuration saved successfully!';
            
            // Check for warnings (BIND startup issues)
            if (data.warning) {
                showWarning(`${message}\n\n⚠️ ${data.warning}`);
                
                // If there are detailed error logs, show them in console
                if (data.bind_error) {
                    console.error('BIND service error details:', data.bind_error);
                }
            } else {
                showSuccess(message);
                
                // If BIND is running, show the zones directory being used
                if (data.zones_directory) {
                    showSuccess(`${message}\n📁 Zones directory: ${data.zones_directory}`);
                }
            }
            
            // Redirect to main page after 3 seconds
            setTimeout(() => {
                window.location.href = '/';
            }, 3000);
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
        bind_config_path: bindConfigPathInput.value.trim() || '/etc/bind/named.conf'
    };
}

function validateConfig(config) {
    // Required fields
    if (!config.bind_host || !config.bind_user) {
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

function showWarning(message) {
    // Use success message element but with warning styling
    successMessage.textContent = message;
    successMessage.style.display = 'block';
    successMessage.style.backgroundColor = '#fff3cd';
    successMessage.style.color = '#856404';
    successMessage.style.borderColor = '#ffeaa7';
    errorMessage.style.display = 'none';
    
    // Auto-hide after 15 seconds (longer for warnings)
    setTimeout(() => {
        successMessage.style.display = 'none';
        // Reset to success styling
        successMessage.style.backgroundColor = '';
        successMessage.style.color = '';
        successMessage.style.borderColor = '';
    }, 15000);
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

// BIND Installation Functions
async function installBind() {
    const config = getFormData();
    
    // Validate required fields
    if (!config.bind_host || !config.bind_user) {
        showError('Please fill in host and user fields before installing BIND');
        return false;
    }
    
    if (!config.bind_ssh_key && !config.bind_password) {
        showError('Please provide authentication (SSH key or password) before installing BIND');
        return false;
    }
    
    // Show installation modal
    showInstallModal();
    
    try {
        const response = await fetch(`${API_BASE_URL}/install-bind`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config),
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Installation request failed');
        }
        
        // Read the streaming response
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const lines = decoder.decode(value).split('\n');
            for (const line of lines) {
                if (line.trim()) {
                    try {
                        const progress = JSON.parse(line);
                        updateInstallStep(progress);
                    } catch (e) {
                        console.error('Failed to parse progress:', e);
                    }
                }
            }
        }
        
        return true;
    } catch (error) {
        console.error('Installation error:', error);
        updateInstallStep({
            step: 'error',
            status: 'error',
            message: `Installation failed: ${error.message}`
        });
        return false;
    }
}

function showInstallModal() {
    installSteps.innerHTML = '';
    closeInstallModalBtn.style.display = 'none';
    installModal.classList.add('active');
}

function closeInstallModal() {
    installModal.classList.remove('active');
}

function updateInstallStep(progress) {
    const { step, status, message } = progress;
    
    // Check if step already exists
    let stepElement = document.getElementById(`install-step-${step}`);
    
    if (!stepElement) {
        // Create new step element
        stepElement = document.createElement('div');
        stepElement.id = `install-step-${step}`;
        stepElement.className = 'install-step';
        
        const iconHtml = status === 'running' 
            ? '<div class="spinner"></div>'
            : status === 'success'
            ? '<svg class="install-step-icon" style="color: #10b981;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>'
            : status === 'error'
            ? '<svg class="install-step-icon" style="color: #ef4444;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>'
            : '<div style="width: 1.5rem; height: 1.5rem;"></div>';
        
        stepElement.innerHTML = `
            ${iconHtml}
            <div class="install-step-content">
                <div class="install-step-title">${getStepTitle(step)}</div>
                <div class="install-step-details">${message}</div>
            </div>
        `;
        
        installSteps.appendChild(stepElement);
    } else {
        // Update existing step
        const iconContainer = stepElement.querySelector(':first-child');
        const detailsElement = stepElement.querySelector('.install-step-details');
        
        if (status === 'running') {
            iconContainer.innerHTML = '<div class="spinner"></div>';
        } else if (status === 'success') {
            iconContainer.innerHTML = '<svg class="install-step-icon" style="color: #10b981;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>';
        } else if (status === 'error') {
            iconContainer.innerHTML = '<svg class="install-step-icon" style="color: #ef4444;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>';
        }
        
        detailsElement.textContent = message;
    }
    
    // Update step class
    stepElement.className = 'install-step';
    if (status === 'running') {
        stepElement.classList.add('active');
    } else if (status === 'success') {
        stepElement.classList.add('success');
    } else if (status === 'error') {
        stepElement.classList.add('error');
    }
    
    // Show close button on completion or error
    if (step === 'complete' || step === 'error' || status === 'error') {
        closeInstallModalBtn.style.display = 'inline-block';
    }
}

function getStepTitle(step) {
    const titles = {
        'connect': '🔌 Connecting to Server',
        'detect_os': '🖥️ Detecting Operating System',
        'check_bind': '🔍 Checking BIND Installation',
        'install': '📦 Installing BIND',
        'enable_service': '⚙️ Enabling BIND Service',
        'verify': '✅ Verifying Installation',
        'complete': '🎉 Complete',
        'error': '❌ Error'
    };
    return titles[step] || step;
}
