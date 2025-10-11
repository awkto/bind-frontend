from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv, set_key
import os
import json
import paramiko
from io import StringIO
import dns.zone
import dns.rdatatype
from dns.exception import DNSException

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='static')
CORS(app)

# BIND DNS credentials and configuration (mutable for runtime updates)
config = {
    'BIND_HOST': os.getenv('BIND_HOST'),
    'BIND_PORT': os.getenv('BIND_PORT', '22'),
    'BIND_USER': os.getenv('BIND_USER'),
    'BIND_SSH_KEY': os.getenv('BIND_SSH_KEY'),
    'BIND_PASSWORD': os.getenv('BIND_PASSWORD'),
    'BIND_CONFIG_PATH': os.getenv('BIND_CONFIG_PATH', '/etc/bind/named.conf')
}

def is_config_complete():
    """Check if all required configuration is present"""
    required = ['BIND_HOST', 'BIND_USER', 'BIND_CONFIG_PATH']
    if not all([config.get(key) for key in required]):
        return False
    # Must have either SSH key or password
    return bool(config.get('BIND_SSH_KEY') or config.get('BIND_PASSWORD'))

def update_config(new_config):
    """Update the configuration in memory and .env file"""
    global config
    
    config.update(new_config)
    
    # Save to .env file
    env_file = '.env'
    if not os.path.exists(env_file):
        with open(env_file, 'w') as f:
            f.write('')
    
    for key, value in new_config.items():
        if value:  # Only save non-empty values
            set_key(env_file, key, str(value))

def get_ssh_client():
    """Create and return an SSH client connection to BIND server"""
    if not is_config_complete():
        raise ValueError("BIND DNS configuration is incomplete")
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        port = int(config.get('BIND_PORT', 22))
        
        if config.get('BIND_SSH_KEY'):
            # Use SSH key authentication
            key_path = os.path.expanduser(config['BIND_SSH_KEY'])
            private_key = paramiko.RSAKey.from_private_key_file(key_path)
            ssh.connect(
                hostname=config['BIND_HOST'],
                port=port,
                username=config['BIND_USER'],
                pkey=private_key,
                timeout=10
            )
        elif config.get('BIND_PASSWORD'):
            # Use password authentication
            ssh.connect(
                hostname=config['BIND_HOST'],
                port=port,
                username=config['BIND_USER'],
                password=config['BIND_PASSWORD'],
                timeout=10
            )
        else:
            raise ValueError("No authentication method configured (SSH key or password)")
        
        return ssh
    except Exception as e:
        raise Exception(f"Failed to connect to BIND server: {str(e)}")

def install_bind_on_server(ssh_config):
    """
    Install BIND on the target server. Yields progress updates.
    ssh_config should contain: host, port, user, ssh_key or password
    """
    ssh = None
    try:
        # Step 1: Connect to server
        yield {'step': 'connect', 'status': 'running', 'message': 'Connecting to server...'}
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        port = int(ssh_config.get('port', 22))
        if ssh_config.get('ssh_key'):
            key_path = os.path.expanduser(ssh_config['ssh_key'])
            private_key = paramiko.RSAKey.from_private_key_file(key_path)
            ssh.connect(
                hostname=ssh_config['host'],
                port=port,
                username=ssh_config['user'],
                pkey=private_key,
                timeout=10
            )
        elif ssh_config.get('password'):
            ssh.connect(
                hostname=ssh_config['host'],
                port=port,
                username=ssh_config['user'],
                password=ssh_config['password'],
                timeout=10
            )
        else:
            yield {'step': 'connect', 'status': 'error', 'message': 'No authentication method provided'}
            return
        
        yield {'step': 'connect', 'status': 'success', 'message': 'Connected successfully'}
        
        # Step 2: Detect OS
        yield {'step': 'detect_os', 'status': 'running', 'message': 'Detecting operating system...'}
        
        stdin, stdout, stderr = ssh.exec_command('cat /etc/os-release')
        os_release = stdout.read().decode('utf-8')
        
        os_type = None
        os_name = ''
        if 'ubuntu' in os_release.lower() or 'debian' in os_release.lower():
            os_type = 'deb'
            os_name = 'Debian/Ubuntu'
        elif 'rhel' in os_release.lower() or 'centos' in os_release.lower() or 'fedora' in os_release.lower() or 'red hat' in os_release.lower():
            os_type = 'rpm'
            if 'fedora' in os_release.lower():
                os_name = 'Fedora'
            else:
                os_name = 'RHEL/CentOS'
        
        if not os_type:
            yield {'step': 'detect_os', 'status': 'error', 'message': 'Unsupported operating system'}
            return
        
        yield {'step': 'detect_os', 'status': 'success', 'message': f'Detected {os_name}'}
        
        # Step 3: Check if BIND is already installed
        yield {'step': 'check_bind', 'status': 'running', 'message': 'Checking if BIND is already installed...'}
        
        if os_type == 'deb':
            stdin, stdout, stderr = ssh.exec_command('dpkg -l | grep bind9')
        else:
            stdin, stdout, stderr = ssh.exec_command('rpm -qa | grep bind')
        
        existing_bind = stdout.read().decode('utf-8')
        if existing_bind and 'bind' in existing_bind:
            yield {'step': 'check_bind', 'status': 'success', 'message': 'BIND is already installed'}
            yield {'step': 'complete', 'status': 'success', 'message': 'BIND installation verified'}
            return
        
        yield {'step': 'check_bind', 'status': 'success', 'message': 'BIND not found, proceeding with installation'}
        
        # Step 4: Install BIND
        yield {'step': 'install', 'status': 'running', 'message': f'Installing BIND on {os_name}...'}
        
        if os_type == 'deb':
            # Update package lists
            stdin, stdout, stderr = ssh.exec_command('sudo apt-get update')
            stdout.channel.recv_exit_status()  # Wait for command to complete
            
            # Install BIND
            stdin, stdout, stderr = ssh.exec_command('sudo DEBIAN_FRONTEND=noninteractive apt-get install -y bind9 bind9utils bind9-doc')
            exit_status = stdout.channel.recv_exit_status()
            install_output = stdout.read().decode('utf-8')
            install_error = stderr.read().decode('utf-8')
            
            if exit_status != 0:
                yield {'step': 'install', 'status': 'error', 'message': f'Installation failed: {install_error}'}
                return
        
        elif os_type == 'rpm':
            # Determine package manager
            stdin, stdout, stderr = ssh.exec_command('which dnf')
            has_dnf = stdout.read().decode('utf-8').strip()
            pkg_manager = 'dnf' if has_dnf else 'yum'
            
            # Install BIND
            stdin, stdout, stderr = ssh.exec_command(f'sudo {pkg_manager} install -y bind bind-utils')
            exit_status = stdout.channel.recv_exit_status()
            install_output = stdout.read().decode('utf-8')
            install_error = stderr.read().decode('utf-8')
            
            if exit_status != 0:
                yield {'step': 'install', 'status': 'error', 'message': f'Installation failed: {install_error}'}
                return
        
        yield {'step': 'install', 'status': 'success', 'message': 'BIND installed successfully'}
        
        # Step 5: Enable and start BIND service
        yield {'step': 'enable_service', 'status': 'running', 'message': 'Enabling BIND service...'}
        
        if os_type == 'deb':
            service_name = 'bind9'
        else:
            service_name = 'named'
        
        # Enable service
        stdin, stdout, stderr = ssh.exec_command(f'sudo systemctl enable {service_name}')
        stdout.channel.recv_exit_status()
        
        # Start service
        stdin, stdout, stderr = ssh.exec_command(f'sudo systemctl start {service_name}')
        exit_status = stdout.channel.recv_exit_status()
        
        if exit_status != 0:
            service_error = stderr.read().decode('utf-8')
            yield {'step': 'enable_service', 'status': 'error', 'message': f'Failed to start service: {service_error}'}
            return
        
        yield {'step': 'enable_service', 'status': 'success', 'message': f'BIND service ({service_name}) started successfully'}
        
        # Step 6: Verify installation
        yield {'step': 'verify', 'status': 'running', 'message': 'Verifying BIND installation...'}
        
        stdin, stdout, stderr = ssh.exec_command(f'sudo systemctl status {service_name}')
        status_output = stdout.read().decode('utf-8')
        
        if 'active (running)' in status_output:
            yield {'step': 'verify', 'status': 'success', 'message': 'BIND is running correctly'}
            yield {'step': 'complete', 'status': 'success', 'message': 'Installation completed successfully!'}
        else:
            yield {'step': 'verify', 'status': 'error', 'message': 'BIND installed but not running properly'}
        
    except Exception as e:
        yield {'step': 'error', 'status': 'error', 'message': f'Installation failed: {str(e)}'}
    finally:
        if ssh:
            ssh.close()

def discover_zones():
    """Discover all zones from BIND configuration files"""
    ssh = None
    try:
        ssh = get_ssh_client()
        
        zones = {}
        config_path = config.get('BIND_CONFIG_PATH', '/etc/bind/named.conf')
        
        # Read the main configuration file
        stdin, stdout, stderr = ssh.exec_command(f'cat {config_path}')
        config_data = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        if error and 'No such file' in error:
            # Try alternative paths
            for alt_path in ['/etc/named.conf', '/var/named/named.conf']:
                stdin, stdout, stderr = ssh.exec_command(f'cat {alt_path}')
                config_data = stdout.read().decode('utf-8')
                error = stderr.read().decode('utf-8')
                if not error or 'No such file' not in error:
                    config['BIND_CONFIG_PATH'] = alt_path
                    break
        
        # Parse zone definitions
        # Look for patterns like: zone "example.com" { ... file "/path/to/file"; ... };
        import re
        
        # First, handle include statements
        include_pattern = r'include\s+"([^"]+)"'
        includes = re.findall(include_pattern, config_data)
        
        all_config_data = config_data
        for include_file in includes:
            stdin, stdout, stderr = ssh.exec_command(f'cat {include_file}')
            included_data = stdout.read().decode('utf-8')
            all_config_data += "\n" + included_data
        
        # Find zone definitions
        zone_pattern = r'zone\s+"([^"]+)"\s+(?:IN\s+)?{([^}]+)}'
        zone_matches = re.finditer(zone_pattern, all_config_data, re.MULTILINE | re.DOTALL)
        
        for match in zone_matches:
            zone_name = match.group(1)
            zone_block = match.group(2)
            
            # Skip special zones
            if zone_name in ['localhost', '0.0.127.in-addr.arpa', '255.in-addr.arpa']:
                continue
            
            # Extract zone type and file path
            type_match = re.search(r'type\s+(master|slave|hint|forward)', zone_block)
            file_match = re.search(r'file\s+"([^"]+)"', zone_block)
            
            zone_type = type_match.group(1) if type_match else 'unknown'
            
            # Only include master zones (ones we can edit)
            if zone_type == 'master' and file_match:
                zone_file = file_match.group(1)
                
                # Handle relative paths
                if not zone_file.startswith('/'):
                    # Assume relative to /var/named or /etc/bind
                    for base_dir in ['/var/named', '/etc/bind', '/var/cache/bind']:
                        test_path = f'{base_dir}/{zone_file}'
                        stdin, stdout, stderr = ssh.exec_command(f'test -f {test_path} && echo "exists"')
                        exists = stdout.read().decode('utf-8').strip()
                        if exists == 'exists':
                            zone_file = test_path
                            break
                
                zones[zone_name] = {
                    'name': zone_name,
                    'type': zone_type,
                    'file': zone_file
                }
        
        return zones
    finally:
        if ssh:
            ssh.close()

def read_zone_file(zone_name=None, zone_file_path=None):
    """Read and parse the BIND zone file via SSH"""
    ssh = None
    try:
        ssh = get_ssh_client()
        
        # If zone_name is provided, discover the file path
        if zone_name and not zone_file_path:
            zones = discover_zones()
            if zone_name not in zones:
                raise Exception(f"Zone not found: {zone_name}")
            zone_file_path = zones[zone_name]['file']
        
        if not zone_file_path:
            raise ValueError("Zone file path is required")
        
        # Read the zone file
        stdin, stdout, stderr = ssh.exec_command(f'cat {zone_file_path}')
        zone_data = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        if error and 'No such file' in error:
            raise Exception(f"Zone file not found: {zone_file_path}")
        
        if not zone_data:
            raise Exception(f"Zone file is empty or could not be read: {zone_file_path}")
        
        return zone_data
    finally:
        if ssh:
            ssh.close()

def parse_zone_data(zone_data, zone_name):
    """Parse BIND zone file data and return structured records"""
    try:
        zone = dns.zone.from_text(zone_data, origin=zone_name, check_origin=False)
        records = []
        
        for name, node in zone.nodes.items():
            name_str = str(name)
            if name_str == '@':
                name_str = '@'
            elif name_str.endswith('.'):
                name_str = name_str[:-1]
            
            for rdataset in node.rdatasets:
                record_type = dns.rdatatype.to_text(rdataset.rdtype)
                ttl = rdataset.ttl
                
                values = []
                for rdata in rdataset:
                    rdata_str = str(rdata)
                    
                    # Format specific record types
                    if record_type == 'MX':
                        # MX records come as "priority exchange"
                        values.append(rdata_str.replace(' ', ' ', 1))
                    elif record_type == 'SOA':
                        # Skip SOA records for now (they're complex)
                        continue
                    else:
                        values.append(rdata_str)
                
                if values:  # Only add if we have values
                    fqdn = f"{name_str}.{zone_name}" if name_str != '@' else zone_name
                    records.append({
                        'name': name_str,
                        'type': record_type,
                        'ttl': ttl,
                        'values': values,
                        'fqdn': fqdn,
                        'id': f"{name_str}_{record_type}"  # Synthetic ID for BIND
                    })
        
        return records
    except DNSException as e:
        raise Exception(f"Failed to parse zone file: {str(e)}")

def write_zone_file(zone_data, zone_name=None, zone_file_path=None):
    """Write updated zone file to BIND server via SSH"""
    ssh = None
    try:
        ssh = get_ssh_client()
        
        # If zone_name is provided, discover the file path
        if zone_name and not zone_file_path:
            zones = discover_zones()
            if zone_name not in zones:
                raise Exception(f"Zone not found: {zone_name}")
            zone_file_path = zones[zone_name]['file']
        
        if not zone_file_path:
            raise ValueError("Zone file path is required")
        
        # Create a temporary file and write to it
        temp_path = f"{zone_file_path}.tmp"
        
        # Write zone data to temp file
        sftp = ssh.open_sftp()
        with sftp.file(temp_path, 'w') as f:
            f.write(zone_data)
        sftp.close()
        
        # Validate the zone file with named-checkzone
        stdin, stdout, stderr = ssh.exec_command(f'named-checkzone {zone_name} {temp_path}')
        check_output = stdout.read().decode('utf-8')
        check_error = stderr.read().decode('utf-8')
        
        if 'OK' not in check_output:
            ssh.exec_command(f'rm {temp_path}')
            raise Exception(f"Zone file validation failed: {check_error}")
        
        # Move temp file to actual zone file
        ssh.exec_command(f'mv {temp_path} {zone_file_path}')
        
        # Reload the zone
        stdin, stdout, stderr = ssh.exec_command(f'rndc reload {zone_name}')
        reload_output = stdout.read().decode('utf-8')
        reload_error = stderr.read().decode('utf-8')
        
        if 'zone reload up-to-date' not in reload_output.lower() and 'reload' not in reload_output.lower():
            print(f"Warning: Zone reload may have issues: {reload_error}")
        
        return True
    finally:
        if ssh:
            ssh.close()

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

@app.route('/api/zones', methods=['GET'])
def get_zones():
    """Get all available DNS zones"""
    try:
        if not is_config_complete():
            return jsonify({'error': 'BIND DNS configuration is incomplete. Please configure your credentials.'}), 400
        
        zones = discover_zones()
        zones_list = list(zones.values())
        
        return jsonify({'zones': zones_list, 'count': len(zones_list)})
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR: {str(e)}")
        print(error_details)
        return jsonify({'error': str(e), 'details': error_details}), 500

@app.route('/api/config/status', methods=['GET'])
def config_status():
    """Check if BIND DNS configuration is complete"""
    try:
        complete = is_config_complete()
        return jsonify({
            'configured': complete
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration (with masked sensitive data)"""
    try:
        return jsonify({
            'bind_host': config.get('BIND_HOST', ''),
            'bind_port': config.get('BIND_PORT', '22'),
            'bind_user': config.get('BIND_USER', ''),
            'bind_config_path': config.get('BIND_CONFIG_PATH', '/etc/bind/named.conf'),
            'auth_method': 'ssh_key' if config.get('BIND_SSH_KEY') else 'password' if config.get('BIND_PASSWORD') else 'none',
            'has_credentials': bool(config.get('BIND_SSH_KEY') or config.get('BIND_PASSWORD'))
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['POST'])
def save_config():
    """Save BIND DNS configuration"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['bind_host', 'bind_user']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
        
        # Must have either SSH key or password
        if not data.get('bind_ssh_key') and not data.get('bind_password'):
            return jsonify({'error': 'Either SSH key path or password is required'}), 400
        
        # Update configuration
        new_config = {
            'BIND_HOST': data['bind_host'],
            'BIND_PORT': data.get('bind_port', '22'),
            'BIND_USER': data['bind_user'],
            'BIND_CONFIG_PATH': data.get('bind_config_path', '/etc/bind/named.conf')
        }
        
        if data.get('bind_ssh_key'):
            new_config['BIND_SSH_KEY'] = data['bind_ssh_key']
        if data.get('bind_password'):
            new_config['BIND_PASSWORD'] = data['bind_password']
        
        update_config(new_config)
        
        return jsonify({
            'success': True,
            'message': 'Configuration saved successfully'
        })
    except Exception as e:
        print(f"Error saving configuration: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/test', methods=['POST'])
def test_config():
    """Test BIND DNS connection before saving"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['bind_host', 'bind_user']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
        
        # Temporarily update config for testing
        temp_config = config.copy()
        config.update({
            'BIND_HOST': data['bind_host'],
            'BIND_PORT': data.get('bind_port', '22'),
            'BIND_USER': data['bind_user'],
            'BIND_CONFIG_PATH': data.get('bind_config_path', '/etc/bind/named.conf'),
            'BIND_SSH_KEY': data.get('bind_ssh_key'),
            'BIND_PASSWORD': data.get('bind_password')
        })
        
        try:
            # Try to discover zones
            zones = discover_zones()
            
            # Restore original config
            config.update(temp_config)
            
            zone_count = len(zones)
            zone_names = ', '.join(list(zones.keys())[:5])
            if zone_count > 5:
                zone_names += f', ... ({zone_count - 5} more)'
            
            return jsonify({
                'success': True,
                'message': f'Connection successful! Found {zone_count} zone(s): {zone_names}',
                'zone_count': zone_count,
                'zones': list(zones.keys())
            })
        except Exception as test_error:
            # Restore original config
            config.update(temp_config)
            
            error_msg = str(test_error)
            if 'Authentication failed' in error_msg or 'No authentication' in error_msg:
                return jsonify({'error': 'Authentication failed. Please check your credentials.'}), 401
            elif 'Connection refused' in error_msg or 'timed out' in error_msg:
                return jsonify({'error': f'Cannot connect to {data["bind_host"]}. Check host and port.'}), 500
            else:
                return jsonify({'error': f'Connection failed: {error_msg}'}), 500
                
    except Exception as e:
        print(f"Error testing configuration: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/install-bind', methods=['POST'])
def install_bind_endpoint():
    """Install BIND on the target server with progress updates"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['bind_host', 'bind_user']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
        
        # Must have either SSH key or password
        if not data.get('bind_ssh_key') and not data.get('bind_password'):
            return jsonify({'error': 'Either SSH key path or password is required'}), 400
        
        # Prepare SSH config
        ssh_config = {
            'host': data['bind_host'],
            'port': data.get('bind_port', '22'),
            'user': data['bind_user'],
            'ssh_key': data.get('bind_ssh_key'),
            'password': data.get('bind_password')
        }
        
        # Stream installation progress
        def generate():
            for progress in install_bind_on_server(ssh_config):
                yield json.dumps(progress) + '\n'
        
        return app.response_class(generate(), mimetype='application/x-ndjson')
                
    except Exception as e:
        print(f"Error installing BIND: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/records', methods=['GET'])
def get_records():
    """Get all DNS records from a BIND zone"""
    try:
        # Check if configuration is complete
        if not is_config_complete():
            return jsonify({'error': 'BIND DNS configuration is incomplete. Please configure your credentials.'}), 400
        
        # Get zone name from query parameter
        zone_name = request.args.get('zone')
        if not zone_name:
            return jsonify({'error': 'Zone parameter is required'}), 400
        
        print(f"Attempting to read BIND DNS Zone: {zone_name}")
        
        # Read and parse zone file
        zone_data = read_zone_file(zone_name=zone_name)
        records = parse_zone_data(zone_data, zone_name)
        
        print(f"Successfully retrieved {len(records)} records")
        return jsonify({'records': records, 'zone': zone_name})
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR: {str(e)}")
        print(error_details)
        return jsonify({'error': str(e), 'details': error_details}), 500

@app.route('/api/records', methods=['POST'])
def create_record():
    """Create a new DNS record"""
    try:
        data = request.json
        zone_name = data.get('zone')
        record_name = data.get('name')
        record_type = data.get('type')
        ttl = data.get('ttl', 3600)
        values = data.get('values', [])
        
        if not zone_name or not record_name or not record_type or not values:
            return jsonify({'error': 'Missing required fields: zone, name, type, values'}), 400
        
        if not is_config_complete():
            return jsonify({'error': 'BIND DNS configuration is incomplete.'}), 400
        
        # Read current zone file
        zone_data = read_zone_file(zone_name=zone_name)
        
        # Add new record to zone data
        # This is a simplified approach - in production you'd want more robust zone file manipulation
        new_record_lines = []
        for value in values:
            if record_type == 'MX':
                new_record_lines.append(f"{record_name}\t{ttl}\tIN\t{record_type}\t{value}")
            else:
                new_record_lines.append(f"{record_name}\t{ttl}\tIN\t{record_type}\t{value}")
        
        updated_zone = zone_data + "\n" + "\n".join(new_record_lines) + "\n"
        
        # Write updated zone file
        write_zone_file(updated_zone, zone_name=zone_name)
        
        return jsonify({'message': 'Record created successfully', 'name': record_name}), 201
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/records/<record_type>/<path:record_name>', methods=['PUT'])
def update_record(record_type, record_name):
    """Update an existing DNS record"""
    try:
        data = request.json
        ttl = data.get('ttl', 3600)
        values = data.get('values', [])
        
        if not values:
            return jsonify({'error': 'Missing required field: values'}), 400
        
        if not is_config_complete():
            return jsonify({'error': 'BIND DNS configuration is incomplete.'}), 400
        
        # For BIND, we need to read the zone file, modify it, and write it back
        # This is a simplified implementation
        return jsonify({'error': 'Record updates coming soon - please delete and recreate for now'}), 501
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/records/<record_type>/<path:record_name>', methods=['DELETE'])
def delete_record(record_type, record_name):
    """Delete a DNS record"""
    try:
        if not is_config_complete():
            return jsonify({'error': 'BIND DNS configuration is incomplete.'}), 400
        
        # For BIND, we need to read the zone file, remove the record, and write it back
        # This is a simplified implementation
        return jsonify({'error': 'Record deletion coming soon - please edit zone file manually for now'}), 501
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Check if environment variables are set and log a warning if not
    required_vars = ['BIND_HOST', 'BIND_USER']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"WARNING: Missing environment variables: {', '.join(missing_vars)}")
        print("The application will start, but you need to configure BIND DNS credentials in Settings.")
        print(f"Starting BIND DNS Manager (unconfigured)")
    else:
        print(f"Starting BIND DNS Manager - Multi-zone support enabled")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
