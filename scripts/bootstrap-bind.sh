#!/bin/bash
#
# bootstrap-bind.sh - Install and configure BIND DNS server
# Logs to: ./bind-bootstrap.log
#

LOG_FILE="./bind-bootstrap.log"

# Logging functions
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "$LOG_FILE" >&2
}

log_step() {
    echo "" | tee -a "$LOG_FILE"
    echo "================================" | tee -a "$LOG_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] STEP: $1" | tee -a "$LOG_FILE"
    echo "================================" | tee -a "$LOG_FILE"
}

# Start installation
log_step "Starting BIND DNS Server Installation"

# Step 1: Detect OS
log_step "Detecting Operating System"
if [ -f /etc/os-release ]; then
    . /etc/os-release
    log "OS: $NAME $VERSION"
    log "ID: $ID"
else
    log_error "Cannot detect operating system"
    exit 1
fi

# Determine if Debian-based or RHEL-based
IS_DEBIAN=0
IS_RHEL=0
BIND_SERVICE=""
BIND_PACKAGE=""

case "$ID" in
    ubuntu|debian)
        IS_DEBIAN=1
        BIND_PACKAGE="bind9"
        BIND_SERVICE="bind9"
        log "Detected Debian/Ubuntu-based system"
        ;;
    rhel|centos|fedora|rocky|almalinux)
        IS_RHEL=1
        BIND_PACKAGE="bind"
        BIND_SERVICE="named"
        log "Detected RHEL/CentOS/Fedora-based system"
        ;;
    *)
        log_error "Unsupported operating system: $ID"
        exit 1
        ;;
esac

# Step 2: Check if BIND is already installed
log_step "Checking for existing BIND installation"
if command -v named >/dev/null 2>&1; then
    BIND_VERSION=$(named -v 2>&1 | head -n1)
    log "BIND already installed: $BIND_VERSION"
    
    # Check if service is running
    if systemctl is-active --quiet "$BIND_SERVICE" 2>/dev/null; then
        log "BIND service is already running"
        log_step "Installation Complete (Already Installed)"
        exit 0
    else
        log "BIND installed but service not running, will start it"
    fi
else
    log "BIND not found, will proceed with installation"
fi

# Step 3: Update package cache
log_step "Updating Package Cache"
if [ $IS_DEBIAN -eq 1 ]; then
    log "Running: apt-get update"
    if sudo apt-get update -y >> "$LOG_FILE" 2>&1; then
        log "Package cache updated successfully"
    else
        log_error "Failed to update package cache"
        exit 1
    fi
elif [ $IS_RHEL -eq 1 ]; then
    # Determine package manager (yum or dnf)
    if command -v dnf >/dev/null 2>&1; then
        PKG_MGR="dnf"
    else
        PKG_MGR="yum"
    fi
    log "Running: $PKG_MGR check-update"
    sudo $PKG_MGR check-update -y >> "$LOG_FILE" 2>&1 || true
    log "Package cache updated successfully"
fi

# Step 4: Install BIND
log_step "Installing BIND DNS Server Package"
if [ $IS_DEBIAN -eq 1 ]; then
    log "Running: apt-get install -y $BIND_PACKAGE bind9utils bind9-doc"
    if sudo apt-get install -y $BIND_PACKAGE bind9utils bind9-doc >> "$LOG_FILE" 2>&1; then
        log "BIND installed successfully"
    else
        log_error "Failed to install BIND"
        exit 1
    fi
elif [ $IS_RHEL -eq 1 ]; then
    log "Running: $PKG_MGR install -y $BIND_PACKAGE bind-utils"
    if sudo $PKG_MGR install -y $BIND_PACKAGE bind-utils >> "$LOG_FILE" 2>&1; then
        log "BIND installed successfully"
    else
        log_error "Failed to install BIND"
        exit 1
    fi
fi

# Step 5: Verify installation
log_step "Verifying BIND Installation"
if command -v named >/dev/null 2>&1; then
    BIND_VERSION=$(named -v 2>&1 | head -n1)
    log "BIND verification successful: $BIND_VERSION"
else
    log_error "BIND installation verification failed"
    exit 1
fi

# Step 6: Enable BIND service
log_step "Enabling BIND Service"
log "Running: systemctl enable $BIND_SERVICE"
if sudo systemctl enable "$BIND_SERVICE" >> "$LOG_FILE" 2>&1; then
    log "BIND service enabled successfully"
else
    # Check if already enabled
    if sudo systemctl is-enabled "$BIND_SERVICE" >> "$LOG_FILE" 2>&1; then
        log "BIND service was already enabled"
    else
        log_error "Failed to enable BIND service"
        exit 1
    fi
fi

# Step 7: Start BIND service
log_step "Starting BIND Service"
log "Running: systemctl start $BIND_SERVICE"
if sudo systemctl start "$BIND_SERVICE" >> "$LOG_FILE" 2>&1; then
    log "BIND service started successfully"
else
    log_error "Failed to start BIND service"
    # Try to get service status for debugging
    log "Service status:"
    sudo systemctl status "$BIND_SERVICE" >> "$LOG_FILE" 2>&1 || true
    exit 1
fi

# Step 8: Check service status
log_step "Checking BIND Service Status"
if systemctl is-active --quiet "$BIND_SERVICE"; then
    log "BIND service is running"
    sudo systemctl status "$BIND_SERVICE" --no-pager >> "$LOG_FILE" 2>&1
else
    log_error "BIND service is not running"
    sudo systemctl status "$BIND_SERVICE" --no-pager >> "$LOG_FILE" 2>&1
    exit 1
fi

# Step 9: Display configuration paths
log_step "BIND Configuration Information"
if [ $IS_DEBIAN -eq 1 ]; then
    log "Main config: /etc/bind/named.conf"
    log "Zone files: /etc/bind/ or /var/cache/bind/"
elif [ $IS_RHEL -eq 1 ]; then
    log "Main config: /etc/named.conf"
    log "Zone files: /var/named/"
fi

log_step "Installation Complete Successfully!"
log "BIND DNS Server is installed and running"
exit 0
