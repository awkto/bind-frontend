// Use relative URL so it works regardless of hostname/IP
const API_BASE_URL = '/api';

// Get server ID from URL parameter
const urlParams = new URLSearchParams(window.location.search);
const serverId = urlParams.get('server');

// DOM Elements
const bindOptionsForm = document.getElementById('bindOptionsForm');
const resetBtn = document.getElementById('resetBtn');
const successMessage = document.getElementById('successMessage');
const errorMessage = document.getElementById('errorMessage');
const loadingMessage = document.getElementById('loadingMessage');
const serverName = document.getElementById('serverName');
const darkModeToggle = document.getElementById('darkModeToggle');
const moonIcon = document.getElementById('moonIcon');
const sunIcon = document.getElementById('sunIcon');

// Default BIND options
const defaultOptions = {
    recursion: true,
    forwarders: ['8.8.8.8', '8.8.4.4'],
    forwardType: 'first',
    maxCacheTtl: 86400,
    maxNcacheTtl: 3600,
    maxClients: 1000,
    recursiveClients: 1000,
    dnssecValidation: true,
    allowQuery: ['any'],
    allowRecursion: ['192.168.0.0/16', '10.0.0.0/8', '172.16.0.0/12'],
    queryLog: false,
    listenOnV4: ['any'],
    listenOnV6: ['any']
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initDarkMode();
    
    if (!serverId) {
        showError('No server specified. Please select a server from the Manage Servers page.');
        return;
    }
    
    loadBindOptions();
    
    bindOptionsForm.addEventListener('submit', handleSaveOptions);
    resetBtn.addEventListener('click', handleReset);
    darkModeToggle.addEventListener('click', toggleDarkMode);
});

// Dark Mode
function initDarkMode() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        enableDarkMode();
    }
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

// Load BIND options
async function loadBindOptions() {
    try {
        loadingMessage.style.display = 'block';
        
        const response = await fetch(`${API_BASE_URL}/servers/${serverId}/bind-options`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to load BIND options');
        }
        
        // Update server name display
        serverName.textContent = `Server: ${data.server_name}`;
        
        // Populate form with loaded options (or defaults if empty)
        const options = Object.keys(data.bind_options).length > 0 
            ? data.bind_options 
            : defaultOptions;
        
        populateForm(options);
        
        loadingMessage.style.display = 'none';
    } catch (error) {
        console.error('Failed to load BIND options:', error);
        showError(`Failed to load BIND options: ${error.message}`);
        loadingMessage.style.display = 'none';
    }
}

// Populate form with options
function populateForm(options) {
    // Recursion & Forwarding
    document.getElementById('recursion').checked = options.recursion !== false;
    document.getElementById('forwarders').value = Array.isArray(options.forwarders) 
        ? options.forwarders.join('\n') 
        : '';
    document.getElementById('forwardType').value = options.forwardType || 'first';
    
    // Caching
    document.getElementById('maxCacheTtl').value = options.maxCacheTtl || '';
    document.getElementById('maxNcacheTtl').value = options.maxNcacheTtl || '';
    
    // Query & Rate Limiting
    document.getElementById('maxClients').value = options.maxClients || '';
    document.getElementById('recursiveClients').value = options.recursiveClients || '';
    document.getElementById('dnssecValidation').checked = options.dnssecValidation !== false;
    
    // Access Control
    document.getElementById('allowQuery').value = Array.isArray(options.allowQuery)
        ? options.allowQuery.join('\n')
        : '';
    document.getElementById('allowRecursion').value = Array.isArray(options.allowRecursion)
        ? options.allowRecursion.join('\n')
        : '';
    
    // Logging
    document.getElementById('queryLog').checked = options.queryLog === true;
    
    // Advanced Options
    document.getElementById('listenOnV4').value = Array.isArray(options.listenOnV4)
        ? options.listenOnV4.join('\n')
        : '';
    document.getElementById('listenOnV6').value = Array.isArray(options.listenOnV6)
        ? options.listenOnV6.join('\n')
        : '';
}

// Get form data
function getFormData() {
    const forwarders = document.getElementById('forwarders').value
        .split('\n')
        .map(f => f.trim())
        .filter(f => f.length > 0);
    
    const allowQuery = document.getElementById('allowQuery').value
        .split('\n')
        .map(a => a.trim())
        .filter(a => a.length > 0);
    
    const allowRecursion = document.getElementById('allowRecursion').value
        .split('\n')
        .map(a => a.trim())
        .filter(a => a.length > 0);
    
    const listenOnV4 = document.getElementById('listenOnV4').value
        .split('\n')
        .map(l => l.trim())
        .filter(l => l.length > 0);
    
    const listenOnV6 = document.getElementById('listenOnV6').value
        .split('\n')
        .map(l => l.trim())
        .filter(l => l.length > 0);
    
    const options = {
        recursion: document.getElementById('recursion').checked,
        forwardType: document.getElementById('forwardType').value,
        dnssecValidation: document.getElementById('dnssecValidation').checked,
        queryLog: document.getElementById('queryLog').checked
    };
    
    // Only include non-empty values
    if (forwarders.length > 0) options.forwarders = forwarders;
    if (allowQuery.length > 0) options.allowQuery = allowQuery;
    if (allowRecursion.length > 0) options.allowRecursion = allowRecursion;
    if (listenOnV4.length > 0) options.listenOnV4 = listenOnV4;
    if (listenOnV6.length > 0) options.listenOnV6 = listenOnV6;
    
    const maxCacheTtl = document.getElementById('maxCacheTtl').value.trim();
    const maxNcacheTtl = document.getElementById('maxNcacheTtl').value.trim();
    const maxClients = document.getElementById('maxClients').value.trim();
    const recursiveClients = document.getElementById('recursiveClients').value.trim();
    
    if (maxCacheTtl) options.maxCacheTtl = parseInt(maxCacheTtl);
    if (maxNcacheTtl) options.maxNcacheTtl = parseInt(maxNcacheTtl);
    if (maxClients) options.maxClients = parseInt(maxClients);
    if (recursiveClients) options.recursiveClients = parseInt(recursiveClients);
    
    return options;
}

// Handle save options
async function handleSaveOptions(e) {
    e.preventDefault();
    hideMessages();
    
    try {
        const options = getFormData();
        
        const response = await fetch(`${API_BASE_URL}/servers/${serverId}/bind-options`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bind_options: options })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to save BIND options');
        }
        
        showSuccess('✅ BIND options saved successfully! Note: BIND service may need to be restarted for changes to take effect.');
    } catch (error) {
        showError(`Failed to save BIND options: ${error.message}`);
    }
}

// Handle reset
function handleReset() {
    if (confirm('Reset all options to defaults?')) {
        populateForm(defaultOptions);
        showSuccess('Options reset to defaults. Click "Save Configuration" to apply.');
    }
}

// UI Helper functions
function showSuccess(message) {
    successMessage.textContent = message;
    successMessage.style.display = 'block';
    errorMessage.style.display = 'none';
    
    // Scroll to top to see message
    window.scrollTo({ top: 0, behavior: 'smooth' });
    
    setTimeout(() => {
        successMessage.style.display = 'none';
    }, 10000);
}

function showError(message) {
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';
    successMessage.style.display = 'none';
    
    // Scroll to top to see message
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function hideMessages() {
    successMessage.style.display = 'none';
    errorMessage.style.display = 'none';
}
