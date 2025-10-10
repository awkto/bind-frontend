# BIND DNS Manager

A modern web-based GUI for managing ISC BIND DNS zones. This application provides a user-friendly interface to view, add, edit, and delete DNS records by connecting to your BIND DNS server via SSH.

![BIND DNS Manager](https://img.shields.io/badge/BIND-DNS%20Manager-005571?logo=linux)
![Python](https://img.shields.io/badge/Python-3.11+-green)
![Flask](https://img.shields.io/badge/Flask-3.0-lightgrey)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)
![SSH](https://img.shields.io/badge/SSH-Paramiko-orange)

## Features

- 🌐 View all DNS records from BIND zone files
- ➕ Add new DNS records (A, AAAA, CNAME, MX, TXT, NS, etc.)
- ✏️ Edit existing DNS records
- 🗑️ Delete DNS records
- 🔐 Secure SSH authentication (key-based or password)
- 🔄 Automatic zone validation with `named-checkzone`
- ⚡ Zone reload via `rndc` after changes
- ⚙️ Web-based configuration management
- 🎨 Modern, responsive web interface with dark mode
- 🔍 Advanced search and filtering by record type
- ⚡ Real-time updates without page refresh
- 🐳 Docker support for easy deployment

## Quick Start with Docker

The easiest way to run BIND DNS Manager is using Docker:

```bash
docker run -d -p 5000:5000 \
  -e BIND_HOST=your-dns-server.com \
  -e BIND_USER=root \
  -e BIND_SSH_KEY=/root/.ssh/id_rsa \
  -e DNS_ZONE=example.com \
  -e ZONE_FILE_PATH=/etc/bind/zones/db.example.com \
  -v ~/.ssh/id_rsa:/root/.ssh/id_rsa:ro \
  --name bind-dns-manager \
  yourusername/bind-dns-gui:latest
```

Then open `http://localhost:5000` in your browser.

## Architecture

- **Backend**: Python Flask REST API connecting via SSH to BIND server
- **Frontend**: Vanilla HTML/CSS/JavaScript
- **Authentication**: SSH key-based or password authentication
- **DNS Management**: Direct zone file manipulation with validation and reload

```
┌─────────────────┐
│   Web Browser   │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│  Flask Server   │
└────────┬────────┘
         │ SSH (Paramiko)
         ▼
┌─────────────────┐
│  BIND Server    │
│  ├─ Zone Files  │
│  ├─ rndc        │
│  └─ named-check │
└─────────────────┘
```

## Prerequisites

1. **Python 3.11 or higher** (for local development)
2. **Docker** (optional, for containerized deployment)
3. **BIND DNS Server** with SSH access
4. **SSH Credentials** (private key or password)
5. **BIND Server Requirements**:
   - SSH access to the server
   - Read/write permissions to zone files
   - Ability to execute `named-checkzone` command
   - Ability to execute `rndc reload` command

## Setting Up SSH Access to BIND Server

### Option 1: SSH Key Authentication (Recommended)

1. **Generate an SSH key pair** (if you don't have one):
```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/bind_dns_key
```

2. **Copy your public key to the BIND server**:
```bash
ssh-copy-id -i ~/.ssh/bind_dns_key.pub user@your-bind-server.com
```

3. **Test the connection**:
```bash
ssh -i ~/.ssh/bind_dns_key user@your-bind-server.com
```

### Option 2: Password Authentication

Simply use your SSH username and password in the configuration.

### BIND Server User Permissions

The SSH user needs proper permissions on the BIND server:

```bash
# On your BIND server, ensure the user can read zone files
sudo usermod -a -G bind your-ssh-user

# Set proper permissions on zone files
sudo chmod 640 /etc/bind/zones/db.example.com
sudo chown root:bind /etc/bind/zones/db.example.com

# Test if user can read zone files
cat /etc/bind/zones/db.example.com

# Test if user can run rndc
rndc reload example.com
```

## Deployment Options

### Option 1: Docker (Recommended)

#### Pull and Run from Docker Hub

```bash
# Pull the latest image
docker pull yourusername/bind-dns-gui:latest

# Run with environment variables (SSH key authentication)
docker run -d \
  --name bind-dns-manager \
  -p 5000:5000 \
  -e BIND_HOST=dns.example.com \
  -e BIND_PORT=22 \
  -e BIND_USER=root \
  -e BIND_SSH_KEY=/root/.ssh/id_rsa \
  -e DNS_ZONE=example.com \
  -e ZONE_FILE_PATH=/etc/bind/zones/db.example.com \
  -v ~/.ssh/id_rsa:/root/.ssh/id_rsa:ro \
  yourusername/bind-dns-gui:latest

# Or use password authentication
docker run -d \
  --name bind-dns-manager \
  -p 5000:5000 \
  -e BIND_HOST=dns.example.com \
  -e BIND_USER=root \
  -e BIND_PASSWORD=your-password \
  -e DNS_ZONE=example.com \
  -e ZONE_FILE_PATH=/etc/bind/zones/db.example.com \
  yourusername/bind-dns-gui:latest

# Or use a .env file
docker run -d \
  --name bind-dns-manager \
  -p 5000:5000 \
  --env-file .env \
  -v ~/.ssh/id_rsa:/root/.ssh/id_rsa:ro \
  yourusername/bind-dns-gui:latest
```

#### Build Docker Image Locally

```bash
# Clone the repository
git clone https://github.com/awkto/bind-frontend.git
cd bind-frontend

# Build the image
docker build -t bind-dns-manager .

# Run the container
docker run -d -p 5000:5000 \
  --env-file .env \
  -v ~/.ssh/id_rsa:/root/.ssh/id_rsa:ro \
  bind-dns-manager
```

#### Docker Compose

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  bind-dns-manager:
    image: yourusername/bind-dns-gui:latest
    container_name: bind-dns-manager
    ports:
      - "5000:5000"
    environment:
      - BIND_HOST=${BIND_HOST}
      - BIND_PORT=${BIND_PORT:-22}
      - BIND_USER=${BIND_USER}
      - BIND_SSH_KEY=${BIND_SSH_KEY}
      - DNS_ZONE=${DNS_ZONE}
      - ZONE_FILE_PATH=${ZONE_FILE_PATH}
    volumes:
      - ~/.ssh/id_rsa:/root/.ssh/id_rsa:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Then run:
```bash
docker-compose up -d
```

### Option 2: Local Python Installation

### 1. Clone the Repository

```bash
git clone https://github.com/awkto/bind-frontend.git
cd bind-frontend
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy the example environment file and fill in your BIND server details:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
# BIND Server Connection
BIND_HOST=dns.example.com
BIND_PORT=22
BIND_USER=root

# Authentication (choose ONE)
BIND_SSH_KEY=/root/.ssh/id_rsa
# BIND_PASSWORD=your-ssh-password

# DNS Zone Configuration
DNS_ZONE=example.com
ZONE_FILE_PATH=/etc/bind/zones/db.example.com
```

**Important**: Never commit the `.env` file to version control!

### 4. Test Your Connection (Optional)

```bash
python test_connection.py
```

### 5. Run the Application

```bash
python app.py
```

The application will start on `http://localhost:5000`

### 6. Access the GUI

Open your web browser and navigate to:
```
http://localhost:5000
```

## Configuration

### First-Time Setup

When you first access the application:

1. If BIND credentials are not configured, you'll be automatically redirected to the **Settings** page
2. Enter your BIND server connection details:
   - **BIND Server Host**: Hostname or IP address of your DNS server
   - **SSH Port**: SSH port (default: 22)
   - **SSH User**: Username with access to BIND zone files
   - **SSH Private Key Path**: Path to SSH key OR password
   - **DNS Zone**: Domain name (e.g., example.com)
   - **Zone File Path**: Full path to zone file (e.g., `/etc/bind/zones/db.example.com`)
3. Click **Test Connection** to verify your credentials
4. Click **Save Configuration** to persist the settings
5. You'll be redirected to the main page with your DNS records

### Updating Configuration

To update your BIND server credentials later:

1. Click the **⚙️ Settings** button in the header
2. Update the required fields
3. Test and save the new configuration

### Environment Variables

All configuration can be provided via environment variables (useful for Docker):

```env
BIND_HOST=dns.example.com
BIND_PORT=22
BIND_USER=root
BIND_SSH_KEY=/root/.ssh/id_rsa
# BIND_PASSWORD=your-password
DNS_ZONE=example.com
ZONE_FILE_PATH=/etc/bind/zones/db.example.com
```

## Usage Guide

### Viewing DNS Records

The main page displays all DNS records from your BIND zone file in a table format showing:
- Record name and FQDN
- Record type (A, AAAA, CNAME, MX, TXT, NS, etc.)
- TTL (Time To Live)
- Record values

### Adding a New Record

1. Click **Add New Record** button
2. Fill in the form:
   - **Record Name**: Enter the subdomain name (e.g., `www`, `mail`) or `@` for the root domain
   - **Record Type**: Select from A, AAAA, CNAME, MX, or TXT
   - **TTL**: Set Time To Live in seconds (default: 3600)
   - **Values**: Enter record values (one per line)
     - For A records: IP addresses (e.g., `192.168.1.1`)
     - For AAAA records: IPv6 addresses
     - For CNAME: Target domain (e.g., `target.example.com`)
     - For MX: Priority and exchange (e.g., `10 mail.example.com`)
     - For TXT: Text values (e.g., `v=spf1 include:_spf.google.com ~all`)

3. Click **Add Record**
4. The zone file will be validated and reloaded automatically

### Editing a Record

1. Click the **✏️ Edit** button next to any record
2. Modify the TTL or values in the modal dialog
3. Click **Update Record**
4. Zone will be validated and reloaded

**Note**: Update/Delete functionality is partially implemented. For now, you may need to edit the zone file directly for complex changes.

### Deleting a Record

1. Click the **🗑️ Delete** button next to any record
2. Confirm the deletion in the dialog

**Note**: Delete functionality returns 501 (coming soon). Use the BIND server directly for deletions.

### Refreshing Records

Click the **🔄 Refresh** button in the header to reload all records from the BIND server.

## API Endpoints

The backend provides the following REST API endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check and zone info |
| GET | `/api/config/status` | Check if configuration is complete |
| GET | `/api/config` | Get current configuration (masked) |
| POST | `/api/config` | Save BIND server configuration |
| POST | `/api/config/test` | Test BIND server connection |
| GET | `/api/records` | List all DNS records from zone file |
| POST | `/api/records` | Create a new DNS record |
| PUT | `/api/records/<type>/<name>` | Update a DNS record (501 - coming soon) |
| DELETE | `/api/records/<type>/<name>` | Delete a DNS record (501 - coming soon) |

## Project Structure

```
bind-frontend/
├── static/
│   ├── index.html               # Main DNS records page
│   ├── settings.html            # Configuration page
│   ├── app.js                   # Main page JavaScript
│   ├── settings.js              # Settings page JavaScript (needs update)
│   └── styles.css               # Modern CSS with dark mode
├── app.py                       # Flask backend with SSH/BIND integration
├── test_connection.py           # Connection test script
├── requirements.txt             # Python dependencies (paramiko, dnspython)
├── Dockerfile                   # Docker image definition
├── docker-compose.yml           # Docker Compose configuration
├── .dockerignore               # Docker build exclusions
├── .env.example                # Example environment variables
├── .env                        # Your configuration (not in git)
├── .gitignore                  # Git ignore rules
├── CONVERSION_SUMMARY.md       # Conversion notes from DigitalOcean
└── README.md                   # This file
```

## Security Considerations

- ⚠️ This application does not include user authentication for the web interface
- 🔐 SSH credentials are stored in environment variables (never commit `.env` to git)
- 🔑 SSH key-based authentication is strongly recommended over passwords
- 🌐 By default, the app runs on all interfaces (`0.0.0.0`) - consider restricting this in production
- 🔒 Ensure your SSH user has minimal required permissions
- 🚫 Do not expose this application directly to the internet without proper security measures
- 🛡️ Consider using a reverse proxy (nginx/traefik) with authentication
- 📝 All zone changes are validated with `named-checkzone` before applying
- 🔄 Failed zone validations are rejected to prevent breaking DNS

## Troubleshooting

### Docker Issues

**Container won't start**
```bash
# Check container logs
docker logs bind-dns-manager

# Check if port is already in use
netstat -an | grep 5000  # Linux/Mac
netstat -ano | findstr :5000  # Windows
```

**SSH key mount issues**
```bash
# Ensure SSH key has correct permissions
chmod 600 ~/.ssh/id_rsa

# Check if key is mounted correctly in container
docker exec bind-dns-manager ls -la /root/.ssh/
```

**Configuration not persisting**
- For Docker: Use environment variables or mount a volume for the .env file
```bash
docker run -d -p 5000:5000 -v $(pwd)/.env:/app/.env bind-dns-manager
```

### Local Development Issues

**"Module not found" errors**
```bash
pip install -r requirements.txt
```

**"Missing required environment variables" error**
Make sure you've created a `.env` file with all required values or configured via the Settings page.

### BIND Server Connection Issues

**"Authentication failed" error**
- Verify SSH credentials are correct
- Test SSH connection manually: `ssh -i /path/to/key user@host`
- Ensure SSH key has correct permissions (600)
- Check if password authentication is enabled on server if using password

**"Zone file not found" error**
- Verify the zone file path is correct on the BIND server
- Check if SSH user has read permissions to the zone file
- Common locations:
  - Debian/Ubuntu: `/etc/bind/zones/db.example.com`
  - RHEL/CentOS: `/var/named/example.com.zone`

**"Permission denied" when updating records**
- SSH user needs write permissions to zone files
- User must be able to execute `rndc reload`
- Consider adding user to `bind` group: `sudo usermod -a -G bind your-user`

**"named-checkzone command not found"**
- Ensure BIND is installed on the server
- Verify the SSH user's PATH includes BIND binaries
- Try full path: `/usr/sbin/named-checkzone`

### Cannot connect to the application
- Check that the application is running on port 5000
- Verify no firewall is blocking the connection
- Try accessing via `http://127.0.0.1:5000` instead

## Known Limitations

- **Update/Delete records**: Currently returns 501 (Not Implemented)
  - Records can be added, but updates/deletes require zone file editing
  - Full implementation coming in future release
- **SOA Serial**: Serial number is not automatically incremented
  - Manual increment required after changes
- **Single Zone**: Currently supports one zone at a time
  - Multi-zone support planned for future
- **No DNSSEC UI**: DNSSEC records can be viewed but not managed via UI

## Future Enhancements

- [ ] Complete update/delete record functionality
- [ ] Auto-increment SOA serial number on changes
- [ ] Multi-zone support (manage multiple domains)
- [ ] DNSSEC record management
- [ ] Zone file backup before changes
- [ ] Change history and audit logging
- [ ] User authentication and authorization
- [ ] HTTPS/TLS support
- [ ] Batch operations
- [ ] Record import/export (CSV, JSON, BIND format)
- [ ] Zone transfer functionality
- [ ] Support for views and split-horizon DNS
- [ ] Kubernetes deployment manifests
- [ ] Webhook notifications for changes

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is open source and available under the MIT License.

## Acknowledgments

- Built with [Flask](https://flask.palletsprojects.com/)
- SSH connectivity via [Paramiko](http://www.paramiko.org/)
- DNS parsing with [dnspython](https://www.dnspython.org/)
- Inspired by the need for a modern BIND management interface

## Support

- 📖 [Documentation](https://github.com/awkto/bind-frontend)
- 🐛 [Issue Tracker](https://github.com/awkto/bind-frontend/issues)
- 💬 [Discussions](https://github.com/awkto/bind-frontend/discussions)

---

**Note**: This is primarily a development/management tool. For production use, implement proper security measures including user authentication, HTTPS, access controls, and consider running it on an isolated management network.
