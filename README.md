# DigitalOcean DNS GUI Manager

A custom web-based GUI for managing DigitalOcean DNS zones. This application provides a modern, user-friendly interface to view, add, edit, and delete DNS records using DigitalOcean API authentication.

![DigitalOcean DNS Manager](https://img.shields.io/badge/DigitalOcean-DNS%20Manager-0080FF?logo=digitalocean)
![Python](https://img.shields.io/badge/Python-3.11+-green)
![Flask](https://img.shields.io/badge/Flask-3.0-lightgrey)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)

## Features

- 🌐 View all DNS records in a specific DigitalOcean DNS zone
- ➕ Add new DNS records (A, AAAA, CNAME, MX, TXT, NS, SOA, PTR, SRV)
- ✏️ Edit existing DNS records
- 🗑️ Delete DNS records
- 🔐 Secure authentication using DigitalOcean API Token
- ⚙️ Web-based configuration management
- 🎨 Modern, responsive web interface with dark mode
- 🔍 Advanced search and filtering by record type
- ⚡ Real-time updates without page refresh
- 🐳 Docker support for easy deployment

## Quick Start with Docker

The easiest way to run DigitalOcean DNS Manager is using Docker:

```bash
docker run -d -p 5000:5000 \
  -e DO_API_TOKEN=your-api-token \
  -e DO_DNS_ZONE=your-domain.com \
  --name digitalocean-dns-manager \
  yourusername/digitalocean-dns-manager:latest
```

Then open `http://localhost:5000` in your browser.

## Architecture

- **Backend**: Python Flask REST API using DigitalOcean API v2
- **Frontend**: Vanilla HTML/CSS/JavaScript
- **Authentication**: DigitalOcean API Token
- **API**: Direct DNS management via DigitalOcean REST API

## Prerequisites

1. **Python 3.11 or higher** (for local development)
2. **Docker** (optional, for containerized deployment)
3. **DigitalOcean Account** with a DNS Zone
4. **DigitalOcean API Token** with read/write permissions

## Getting Your DigitalOcean API Token

1. Log in to your DigitalOcean account
2. Go to **API** in the left sidebar (https://cloud.digitalocean.com/account/api/tokens)
3. Click **Generate New Token**
4. Give it a name (e.g., "DNS Manager")
5. Select both **Read** and **Write** scopes
6. Click **Generate Token**
7. **Copy the token immediately** - you won't be able to see it again!

## Deployment Options

### Option 1: Docker (Recommended)

#### Pull and Run from Docker Hub

```bash
# Pull the latest image
docker pull yourusername/digitalocean-dns-manager:latest

# Run with environment variables
docker run -d \
  --name digitalocean-dns-manager \
  -p 5000:5000 \
  -e DO_API_TOKEN=your-api-token \
  -e DO_DNS_ZONE=your-domain.com \
  yourusername/digitalocean-dns-manager:latest

# Or use a .env file
docker run -d \
  --name digitalocean-dns-manager \
  -p 5000:5000 \
  --env-file .env \
  yourusername/digitalocean-dns-manager:latest
```

#### Build Docker Image Locally

```bash
# Clone the repository
git clone https://github.com/awkto/digitalocean-dns-gui.git
cd digitalocean-dns-gui

# Build the image
docker build -t digitalocean-dns-manager .

# Run the container
docker run -d -p 5000:5000 --env-file .env digitalocean-dns-manager
```

#### Docker Compose

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  digitalocean-dns-manager:
    image: yourusername/digitalocean-dns-manager:latest
    container_name: digitalocean-dns-manager
    ports:
      - "5000:5000"
    environment:
      - DO_API_TOKEN=${DO_API_TOKEN}
      - DO_DNS_ZONE=${DO_DNS_ZONE}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:5000/api/health')"]
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
git clone https://github.com/awkto/digitalocean-dns-gui.git
cd digitalocean-dns-gui
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy the example environment file and fill in your DigitalOcean credentials:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
# DigitalOcean API Credentials
DO_API_TOKEN=your-digitalocean-api-token-here
DO_DNS_ZONE=your-domain.com
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

1. If DigitalOcean credentials are not configured, you'll be automatically redirected to the **Settings** page
2. Enter your DigitalOcean API credentials:
   - API Token
   - DNS Zone name (e.g., example.com)
3. Click **Test Connection** to verify your credentials
4. Click **Save Configuration** to persist the settings
5. You'll be redirected to the main page with your DNS records

### Updating Configuration

To update your DigitalOcean credentials later:

1. Click the **⚙️ Settings** button in the header
2. Update the required fields
3. Test and save the new configuration

### Environment Variables

All configuration can be provided via environment variables (useful for Docker):

```env
DO_API_TOKEN=dop_v1_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DO_DNS_ZONE=example.com
```

## Usage Guide

### Viewing DNS Records

The main page displays all DNS records in your configured zone in a table format showing:
- Record name and FQDN
- Record type (A, AAAA, CNAME, MX, TXT, etc.)
- TTL (Time To Live)
- Record values

### Adding a New Record

1. Fill in the "Add New DNS Record" form:
   - **Record Name**: Enter the subdomain name (e.g., `www`, `mail`) or `@` for the root domain
   - **Record Type**: Select from A, AAAA, CNAME, MX, or TXT
   - **TTL**: Set Time To Live in seconds (default: 3600)
   - **Values**: Enter record values (one per line)
     - For A records: IP addresses (e.g., `192.168.1.1`)
     - For CNAME: Target domain (e.g., `target.example.com`)
     - For MX: Priority and exchange (e.g., `10 mail.example.com`)
     - For TXT: Text values (e.g., `v=spf1 include:_spf.google.com ~all`)

2. Click "Add Record"

### Editing a Record

1. Click the "✏️ Edit" button next to any record
2. Modify the TTL or values in the modal dialog
3. Click "Update Record"

### Deleting a Record

1. Click the "🗑️ Delete" button next to any record
2. Confirm the deletion in the dialog

### Refreshing Records

Click the "🔄 Refresh" button in the header to reload all records from DigitalOcean.

## API Endpoints

The backend provides the following REST API endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check and zone info |
| GET | `/api/config/status` | Check if configuration is complete |
| GET | `/api/config` | Get current configuration |
| POST | `/api/config` | Save configuration |
| POST | `/api/config/test` | Test DigitalOcean credentials |
| GET | `/api/records` | List all DNS records |
| POST | `/api/records` | Create a new DNS record |
| PUT | `/api/records/<type>/<name>` | Update a DNS record |
| DELETE | `/api/records/<type>/<name>` | Delete a DNS record |

## Project Structure

```
digitalocean-dns-gui/
├── static/
│   ├── index.html               # Main DNS records page
│   ├── settings.html            # Configuration page
│   ├── app.js                   # Main page JavaScript
│   ├── settings.js              # Settings page JavaScript
│   └── styles.css               # Modern CSS with dark mode
├── app.py                       # Flask backend application
├── test_connection.py           # Connection test script
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Docker image definition
├── docker-compose.yml           # Docker Compose configuration
├── .dockerignore               # Docker build exclusions
├── .env.example                # Example environment variables
├── .env                        # Your configuration (not in git)
├── .gitignore                  # Git ignore rules
└── README.md                   # This file
```

## Security Considerations

- ⚠️ This application does not include user authentication for the web interface
- 🔐 DigitalOcean API token is stored in environment variables (never commit `.env` to git)
- 🌐 By default, the app runs on all interfaces (`0.0.0.0`) - consider restricting this in production
- 🔒 Ensure your API token has minimal required permissions
- 🚫 Do not expose this application directly to the internet without proper security measures

## Troubleshooting

### Docker Issues

**Container won't start**
```bash
# Check container logs
docker logs digitalocean-dns-manager

# Check if port is already in use
netstat -an | grep 5000  # Linux/Mac
netstat -ano | findstr :5000  # Windows
```

**Configuration not persisting**
- For Docker: Use environment variables or mount a volume for the .env file
```bash
docker run -d -p 5000:5000 -v $(pwd)/.env:/app/.env digitalocean-dns-manager
```

### Local Development Issues

**"Module not found" errors**
```bash
pip install -r requirements.txt
```

**"Missing required environment variables" error**
Make sure you've created a `.env` file with all required values or configured via the Settings page.

### DigitalOcean API authentication fails
- Verify your API token is correct and not expired
- Check that the API token has both read and write permissions
- Ensure the DNS zone name is correct (e.g., `example.com`, not `www.example.com`)
- Verify the domain exists in your DigitalOcean account

### Cannot connect to the application
- Check that the application is running on port 5000
- Verify no firewall is blocking the connection
- Try accessing via `http://127.0.0.1:5000` instead

## Future Enhancements

- [x] User-friendly configuration management UI
- [x] Dark mode support
- [x] Advanced search and filtering
- [x] Docker containerization
- [ ] CI/CD pipeline for automated releases
- [ ] User authentication and authorization
- [ ] HTTPS/TLS support
- [ ] Batch operations
- [ ] Record import/export (CSV, JSON)
- [ ] Audit logging and change history
- [ ] Multi-zone support
- [ ] Kubernetes deployment manifests
- [ ] Webhook notifications

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the MIT License.

## Acknowledgments

- Built with [Flask](https://flask.palletsprojects.com/)
- DigitalOcean integration via [DigitalOcean API v2](https://docs.digitalocean.com/reference/api/api-reference/)
- Icons: Emoji characters for simplicity

---

**Note**: This is a development tool. For production use, implement proper security measures including user authentication, HTTPS, and access controls.
