// Use relative URL so it works regardless of hostname/IP
const API_BASE_URL = '/api';

// DOM Elements
const addServerBtn = document.getElementById('addServerBtn');
const serverModal = document.getElementById('serverModal');
const serverForm = document.getElementById('serverForm');
const cancelBtn = document.getElementById('cancelBtn');
const serversTableBody = document.getElementById('serversTableBody');
const loadingIndicator = document.getElementById('loadingIndicator');
const successMessage = document.getElementById('successMessage');
const errorMessage = document.getElementById('errorMessage');
const modalError = document.getElementById('modalError');
const modalSuccess = document.getElementById('modalSuccess');
const modalTitle = document.getElementById('modalTitle');
const darkModeToggle = document.getElementById('darkModeToggle');
const moonIcon = document.getElementById('moonIcon');
const sunIcon = document.getElementById('sunIcon');

// State
let servers = [];
let activeServerId = null;
let editingServerId = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initDarkMode();
    loadServers();
    
    addServerBtn.addEventListener('click', showAddModal);
    cancelBtn.addEventListener('click', hideModal);
    serverForm.addEventListener('submit', handleSaveServer);
    darkModeToggle.addEventListener('click', toggleDarkMode);
    
    // Close modal on backdrop click
    document.querySelector('.modal-backdrop').addEventListener('click', hideModal);
    document.querySelector('.close').addEventListener('click', hideModal);
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

// Load servers
async function loadServers() {
    try {
        loadingIndicator.style.display = 'block';
        
        const response = await fetch(`${API_BASE_URL}/servers`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to load servers');
        }
        
        servers = data.servers;
        activeServerId = data.active_server_id;
        
        displayServers();
        loadingIndicator.style.display = 'none';
    } catch (error) {
        console.error('Failed to load servers:', error);
        showError(`Failed to load servers: ${error.message}`);
        loadingIndicator.style.display = 'none';
    }
}

// Display servers in table
function displayServers() {
    serversTableBody.innerHTML = '';
    
    if (servers.length === 0) {
        serversTableBody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align: center; padding: 3rem; color: var(--color-slate-500);">
                    No servers configured. Click "Add Server" to get started.
                </td>
            </tr>
        `;
        return;
    }
    
    servers.forEach(server => {
        const row = document.createElement('tr');
        const isActive = server.id === activeServerId;
        
        const statusBadge = isActive
            ? '<span class="type-badge" style="background: #10b981; color: white;">Active</span>'
            : '<span class="type-badge" style="background: #6b7280; color: white;">Inactive</span>';
        
        row.innerHTML = `
            <td>
                <div style="font-weight: 500;">${escapeHtml(server.name)}</div>
                ${isActive ? '<div style="font-size: 0.75rem; color: var(--color-emerald-600);">Currently selected</div>' : ''}
            </td>
            <td>
                <div>${escapeHtml(server.host)}:${escapeHtml(server.port)}</div>
            </td>
            <td>${escapeHtml(server.user)}</td>
            <td>${statusBadge}</td>
            <td class="col-actions">
                <div class="actions-group">
                    ${!isActive ? `<button class="btn btn-action" onclick="activateServer('${server.id}')">
                        <svg class="btn-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                        </svg>
                        Activate
                    </button>` : ''}
                    <button class="btn btn-action" onclick="viewBindOptions('${server.id}')">
                        <svg class="btn-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                        </svg>
                        BIND Config
                    </button>
                    <button class="btn btn-action btn-action-edit" onclick="editServer('${server.id}')">
                        <svg class="btn-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                        </svg>
                        Edit
                    </button>
                    <button class="btn btn-action btn-action-delete" onclick="deleteServer('${server.id}', '${escapeHtml(server.name)}')">
                        <svg class="btn-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                        </svg>
                        Delete
                    </button>
                </div>
            </td>
        `;
        
        serversTableBody.appendChild(row);
    });
}

// Show add modal
function showAddModal() {
    editingServerId = null;
    modalTitle.textContent = 'Add Server';
    serverForm.reset();
    document.getElementById('serverId').value = '';
    document.getElementById('serverPort').value = '22';
    document.getElementById('serverConfigPath').value = '/etc/bind/named.conf';
    hideModalMessages();
    serverModal.classList.add('active');
}

// Edit server
function editServer(serverId) {
    const server = servers.find(s => s.id === serverId);
    if (!server) return;
    
    editingServerId = serverId;
    modalTitle.textContent = 'Edit Server';
    
    document.getElementById('serverId').value = server.id;
    document.getElementById('serverName').value = server.name;
    document.getElementById('serverHost').value = server.host;
    document.getElementById('serverPort').value = server.port;
    document.getElementById('serverUser').value = server.user;
    document.getElementById('serverPassword').value = ''; // Don't show password
    document.getElementById('serverSshKey').value = server.ssh_key || '';
    document.getElementById('serverConfigPath').value = server.config_path;
    
    hideModalMessages();
    serverModal.classList.add('active');
}

// Handle save server
async function handleSaveServer(e) {
    e.preventDefault();
    hideModalMessages();
    
    const serverId = document.getElementById('serverId').value;
    const name = document.getElementById('serverName').value.trim();
    const host = document.getElementById('serverHost').value.trim();
    const port = document.getElementById('serverPort').value.trim();
    const user = document.getElementById('serverUser').value.trim();
    const password = document.getElementById('serverPassword').value.trim();
    const ssh_key = document.getElementById('serverSshKey').value.trim();
    const config_path = document.getElementById('serverConfigPath').value.trim();
    
    if (!name || !host || !user) {
        showModalError('Please fill in all required fields');
        return;
    }
    
    if (!ssh_key && !password) {
        showModalError('Either SSH key or password is required');
        return;
    }
    
    try {
        const serverData = {
            name, host, port, user, config_path
        };
        
        if (ssh_key) serverData.ssh_key = ssh_key;
        if (password) serverData.password = password;
        
        const url = serverId 
            ? `${API_BASE_URL}/servers/${serverId}`
            : `${API_BASE_URL}/servers`;
        
        const method = serverId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(serverData)
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to save server');
        }
        
        showModalSuccess('Server saved successfully!');
        setTimeout(() => {
            hideModal();
            loadServers();
            showSuccess(`Server "${name}" ${serverId ? 'updated' : 'added'} successfully`);
        }, 1500);
    } catch (error) {
        showModalError(`Failed to save server: ${error.message}`);
    }
}

// Activate server
async function activateServer(serverId) {
    try {
        const response = await fetch(`${API_BASE_URL}/servers/${serverId}/activate`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to activate server');
        }
        
        showSuccess('Server activated successfully');
        loadServers();
    } catch (error) {
        showError(`Failed to activate server: ${error.message}`);
    }
}

// Delete server
async function deleteServer(serverId, serverName) {
    if (!confirm(`Are you sure you want to delete server "${serverName}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/servers/${serverId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to delete server');
        }
        
        showSuccess(`Server "${serverName}" deleted successfully`);
        loadServers();
    } catch (error) {
        showError(`Failed to delete server: ${error.message}`);
    }
}

// View BIND options
function viewBindOptions(serverId) {
    window.location.href = `/bind-options.html?server=${serverId}`;
}

// Modal functions
function hideModal() {
    serverModal.classList.remove('active');
}

function showModalError(message) {
    modalError.textContent = message;
    modalError.style.display = 'block';
    modalSuccess.style.display = 'none';
}

function showModalSuccess(message) {
    modalSuccess.textContent = message;
    modalSuccess.style.display = 'block';
    modalError.style.display = 'none';
}

function hideModalMessages() {
    modalError.style.display = 'none';
    modalSuccess.style.display = 'none';
}

// UI Helper functions
function showSuccess(message) {
    successMessage.textContent = message;
    successMessage.style.display = 'block';
    errorMessage.style.display = 'none';
    setTimeout(() => {
        successMessage.style.display = 'none';
    }, 5000);
}

function showError(message) {
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';
    successMessage.style.display = 'none';
    setTimeout(() => {
        errorMessage.style.display = 'none';
    }, 5000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
