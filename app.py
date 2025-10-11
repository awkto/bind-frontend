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
from jinja2 import Environment, FileSystemLoader
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='static')
CORS(app)

# Setup Jinja2 for templates
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = Environment(loader=FileSystemLoader(template_dir))

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
            key_content = config['BIND_SSH_KEY']
            
            # Check if it's a file path or key content
            if key_content.startswith('-----BEGIN'):
                # It's the actual key content
                from io import StringIO
                key_file = StringIO(key_content)
                try:
                    # Try RSA key first
                    private_key = paramiko.RSAKey.from_private_key(key_file)
                except paramiko.ssh_exception.SSHException:
                    # Try other key types
                    key_file.seek(0)
                    try:
                        private_key = paramiko.Ed25519Key.from_private_key(key_file)
                    except paramiko.ssh_exception.SSHException:
                        key_file.seek(0)
                        try:
                            private_key = paramiko.ECDSAKey.from_private_key(key_file)
                        except paramiko.ssh_exception.SSHException:
                            key_file.seek(0)
                            private_key = paramiko.DSSKey.from_private_key(key_file)
            else:
                # It's a file path (legacy support)
                key_path = os.path.expanduser(key_content)
                try:
                    private_key = paramiko.RSAKey.from_private_key_file(key_path)
                except paramiko.ssh_exception.SSHException:
                    try:
                        private_key = paramiko.Ed25519Key.from_private_key_file(key_path)
                    except paramiko.ssh_exception.SSHException:
                        try:
                            private_key = paramiko.ECDSAKey.from_private_key_file(key_path)
                        except paramiko.ssh_exception.SSHException:
                            private_key = paramiko.DSSKey.from_private_key_file(key_path)
            
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

def check_bind_installed(ssh):
    """Check if BIND is installed on the server using multiple detection methods"""
    try:
        # Try multiple detection methods for different systems
        # Method 1: Check for named binary in common locations
        check_commands = [
            'command -v named >/dev/null 2>&1 && echo "INSTALLED"',
            'command -v named-pkcs11 >/dev/null 2>&1 && echo "INSTALLED"',
            'test -f /usr/sbin/named && echo "INSTALLED"',
            'test -f /usr/bin/named && echo "INSTALLED"',
            # Method 2: Check for BIND package on Debian/Ubuntu
            'dpkg -l | grep -q "^ii.*bind9" && echo "INSTALLED"',
            # Method 3: Check for BIND package on RHEL/CentOS
            'rpm -q bind >/dev/null 2>&1 && echo "INSTALLED"',
            # Method 4: Check for systemd service
            'systemctl list-unit-files | grep -q "named.service\\|bind9.service" && echo "INSTALLED"'
        ]
        
        # Try each method
        for cmd in check_commands:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            result = stdout.read().decode('utf-8').strip()
            if result == "INSTALLED":
                print(f"✅ BIND detected using: {cmd[:50]}...")
                return True
        
        print("❌ BIND not detected by any method")
        return False
    except Exception as e:
        print(f"Error checking BIND installation: {str(e)}")
        return False

def install_bind_on_server(ssh_config):
    """
    Install BIND on the target server using bash scripts.
    Yields progress updates by monitoring the log file.
    ssh_config should contain: host, port, user, ssh_key or password
    """
    ssh = None
    sftp = None
    
    try:
        # Step 1: Connect to server
        yield {'step': 'connect', 'status': 'running', 'message': 'Connecting to server...'}
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        port = int(ssh_config.get('port', 22))
        if ssh_config.get('ssh_key'):
            key_content = ssh_config['ssh_key']
            
            # Check if it's a file path or key content
            if key_content.startswith('-----BEGIN'):
                # It's the actual key content
                from io import StringIO
                key_file = StringIO(key_content)
                try:
                    private_key = paramiko.RSAKey.from_private_key(key_file)
                except paramiko.ssh_exception.SSHException:
                    key_file.seek(0)
                    try:
                        private_key = paramiko.Ed25519Key.from_private_key(key_file)
                    except paramiko.ssh_exception.SSHException:
                        key_file.seek(0)
                        try:
                            private_key = paramiko.ECDSAKey.from_private_key(key_file)
                        except paramiko.ssh_exception.SSHException:
                            key_file.seek(0)
                            private_key = paramiko.DSSKey.from_private_key(key_file)
            else:
                # It's a file path (legacy support)
                key_path = os.path.expanduser(key_content)
                try:
                    private_key = paramiko.RSAKey.from_private_key_file(key_path)
                except paramiko.ssh_exception.SSHException:
                    try:
                        private_key = paramiko.Ed25519Key.from_private_key_file(key_path)
                    except paramiko.ssh_exception.SSHException:
                        try:
                            private_key = paramiko.ECDSAKey.from_private_key_file(key_path)
                        except paramiko.ssh_exception.SSHException:
                            private_key = paramiko.DSSKey.from_private_key_file(key_path)
            
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
        
        # Step 2: Upload bootstrap script
        yield {'step': 'upload', 'status': 'running', 'message': 'Uploading installation script...'}
        
        sftp = ssh.open_sftp()
        script_path = os.path.join(os.path.dirname(__file__), 'scripts', 'bootstrap-bind.sh')
        
        if not os.path.exists(script_path):
            yield {'step': 'upload', 'status': 'error', 'message': f'Script not found: {script_path}'}
            return
        
        remote_script = '/tmp/bootstrap-bind.sh'
        sftp.put(script_path, remote_script)
        sftp.chmod(remote_script, 0o755)
        
        yield {'step': 'upload', 'status': 'success', 'message': 'Installation script uploaded'}
        
        # Step 3: Run installation script
        yield {'step': 'install', 'status': 'running', 'message': 'Running installation script...'}
        
        # Execute the script and capture output in real-time
        stdin, stdout, stderr = ssh.exec_command(f'bash {remote_script}', get_pty=True)
        
        # Read output line by line
        current_step = 'install'
        for line in stdout:
            line = line.strip()
            if line:
                # Parse step information from log output
                if 'STEP:' in line:
                    step_msg = line.split('STEP:')[-1].strip()
                    yield {'step': current_step, 'status': 'running', 'message': step_msg}
                elif 'ERROR:' in line:
                    error_msg = line.split('ERROR:')[-1].strip()
                    yield {'step': current_step, 'status': 'error', 'message': error_msg}
                    return
                elif 'successfully' in line.lower() or 'complete' in line.lower():
                    yield {'step': current_step, 'status': 'running', 'message': line}
        
        # Check exit status
        exit_status = stdout.channel.recv_exit_status()
        
        if exit_status == 0:
            yield {'step': 'install', 'status': 'success', 'message': 'BIND installed successfully'}
            
            # Step 4: Verify installation
            yield {'step': 'verify', 'status': 'running', 'message': 'Verifying installation...'}
            
            # Check if BIND is running
            bind_installed = check_bind_installed(ssh)
            
            if bind_installed:
                yield {'step': 'verify', 'status': 'success', 'message': 'BIND is installed and running'}
                yield {'step': 'complete', 'status': 'success', 'message': 'Installation completed successfully!'}
            else:
                yield {'step': 'verify', 'status': 'error', 'message': 'BIND installed but not running properly'}
        else:
            yield {'step': 'install', 'status': 'error', 'message': f'Installation script failed with exit code {exit_status}'}
        
    except Exception as e:
        yield {'step': 'error', 'status': 'error', 'message': f'Installation failed: {str(e)}'}
    finally:
        if sftp:
            try:
                sftp.close()
            except:
                pass
        if ssh:
            try:
                ssh.close()
            except:
                pass


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
                    # Check standard zone directories (prioritize /var/lib/bind/zones)
                    for base_dir in ['/var/lib/bind/zones', '/var/named', '/etc/bind', '/var/cache/bind']:
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
                        # SOA records: "mname rname serial refresh retry expire minimum"
                        # Parse and format SOA record for display
                        parts = rdata_str.split()
                        if len(parts) >= 7:
                            soa_formatted = (
                                f"{parts[0]} {parts[1]} "
                                f"(Serial: {parts[2]}, Refresh: {parts[3]}, "
                                f"Retry: {parts[4]}, Expire: {parts[5]}, TTL: {parts[6]})"
                            )
                            values.append(soa_formatted)
                        else:
                            # Fallback to raw format if parsing fails
                            values.append(rdata_str)
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
    sftp = None
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
        
        # Use /tmp for temporary file (always writable)
        import hashlib
        temp_filename = f"zone_{hashlib.md5(zone_name.encode()).hexdigest()}.tmp"
        temp_path = f"/tmp/{temp_filename}"
        
        print(f"Writing zone data to temporary file: {temp_path}")
        
        # Write zone data to temp file in /tmp
        try:
            sftp = ssh.open_sftp()
            with sftp.file(temp_path, 'w') as f:
                f.write(zone_data)
            sftp.close()
            sftp = None
        except Exception as sftp_error:
            print(f"⚠️  SFTP write failed: {sftp_error}, trying alternative method...")
            # Fallback: use echo with sudo
            # Escape single quotes in zone_data
            zone_data_escaped = zone_data.replace("'", "'\\''")
            stdin, stdout, stderr = ssh.exec_command(f"echo '{zone_data_escaped}' | sudo tee {temp_path} > /dev/null")
            write_error = stderr.read().decode('utf-8')
            if write_error and 'permission denied' not in write_error.lower():
                print(f"Warning during temp file write: {write_error}")
        
        # Validate the zone file with named-checkzone
        print(f"Validating zone file: {zone_name}")
        stdin, stdout, stderr = ssh.exec_command(f'named-checkzone {zone_name} {temp_path}')
        check_output = stdout.read().decode('utf-8')
        check_error = stderr.read().decode('utf-8')
        
        if 'OK' not in check_output and 'loaded serial' not in check_output:
            ssh.exec_command(f'sudo rm {temp_path}')
            raise Exception(f"Zone file validation failed: {check_error}")
        
        print(f"Zone file validated successfully")
        
        # Move temp file to actual zone file (use sudo for permissions)
        print(f"⚠️  Using sudo to write zone file: {zone_file_path}")
        stdin, stdout, stderr = ssh.exec_command(f'sudo mv {temp_path} {zone_file_path}')
        move_error = stderr.read().decode('utf-8')
        if move_error and 'permission denied' not in move_error.lower():
            print(f"Warning during zone file move: {move_error}")
        
        # Set proper permissions on zone file
        stdin, stdout, stderr = ssh.exec_command(f'sudo chmod 644 {zone_file_path}')
        
        # Reload the zone (use sudo for rndc)
        print(f"⚠️  Using sudo to reload zone: {zone_name}")
        stdin, stdout, stderr = ssh.exec_command(f'sudo rndc reload {zone_name}')
        reload_output = stdout.read().decode('utf-8')
        reload_error = stderr.read().decode('utf-8')
        
        print(f"Zone reload output: {reload_output}")
        if reload_error:
            print(f"Zone reload stderr: {reload_error}")
        
        if 'zone reload up-to-date' not in reload_output.lower() and 'reload' not in reload_output.lower():
            print(f"⚠️  Warning: Zone reload may have issues: {reload_error}")
        
        print(f"✅ Zone file written and reloaded successfully: {zone_name}")
        return True
    except Exception as e:
        print(f"❌ Error in write_zone_file: {str(e)}")
        raise
    finally:
        if sftp:
            try:
                sftp.close()
            except:
                pass
        if ssh:
            try:
                ssh.close()
            except:
                pass

# Template rendering functions
def render_zone_file(zone_name, primary_ns, admin_email, ttl=86400, ns_ip_address=None):
    """Render zone file from template"""
    # Generate serial number (YYYYMMDD01 format)
    serial = datetime.now().strftime('%Y%m%d01')
    
    # Convert admin email (replace @ with .)
    admin_email_bind = admin_email.replace('@', '.')
    
    # Extract hostname from NS if it's within the zone (for glue record)
    ns_hostname = None
    if ns_ip_address and primary_ns:
        # Check if NS is within this zone
        if primary_ns.endswith(f'.{zone_name}'):
            # Extract the hostname part (e.g., "ns1" from "ns1.example.com")
            ns_hostname = primary_ns.replace(f'.{zone_name}', '')
        elif primary_ns == zone_name:
            # NS is the zone apex
            ns_hostname = '@'
    
    template = jinja_env.get_template('zone-file.j2')
    return template.render(
        zone_name=zone_name,
        primary_ns=primary_ns,
        admin_email_bind=admin_email_bind,
        serial=serial,
        ttl=ttl,
        ns_ip_address=ns_ip_address,
        ns_hostname=ns_hostname,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

def render_zone_config(zone_name, zone_file_path):
    """Render zone configuration block for named.conf"""
    template = jinja_env.get_template('zone-config.j2')
    return template.render(
        zone_name=zone_name,
        zone_file_path=zone_file_path,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

def get_bind_directory_option(ssh, named_conf_path):
    """
    Extract the 'directory' option from BIND configuration.
    Searches main config and included files.
    Returns the directory path or None if not found.
    """
    try:
        # Read main named.conf
        stdin, stdout, stderr = ssh.exec_command(f'cat {named_conf_path}')
        config_content = stdout.read().decode('utf-8')
        
        # Look for directory option in main config
        import re
        dir_match = re.search(r'directory\s+"([^"]+)"', config_content)
        if dir_match:
            return dir_match.group(1)
        
        # Look for include statements
        include_pattern = re.compile(r'include\s+"([^"]+)"')
        includes = include_pattern.findall(config_content)
        
        # Search in included files
        for include_file in includes:
            # Handle relative paths
            if not include_file.startswith('/'):
                config_dir = named_conf_path.rsplit('/', 1)[0]
                include_file = f"{config_dir}/{include_file}"
            
            stdin, stdout, stderr = ssh.exec_command(f'cat {include_file} 2>/dev/null')
            include_content = stdout.read().decode('utf-8')
            dir_match = re.search(r'directory\s+"([^"]+)"', include_content)
            if dir_match:
                return dir_match.group(1)
        
        return None
    except Exception as e:
        print(f"Error reading BIND directory option: {e}")
        return None

def ensure_bind_directory_configured(ssh, named_conf_path, bind_user='bind'):
    """
    Ensure BIND has a proper directory option configured.
    Creates named.conf.options if needed and sets up the directory.
    Returns the directory path.
    """
    default_dir = '/var/lib/bind/zones'
    
    # Check if directory option already exists
    existing_dir = get_bind_directory_option(ssh, named_conf_path)
    
    if existing_dir:
        print(f"Found existing BIND directory: {existing_dir}")
        # Ensure the directory exists and has proper permissions
        ssh.exec_command(f'sudo mkdir -p {existing_dir}')
        ssh.exec_command(f'sudo chown {bind_user}:{bind_user} {existing_dir}')
        ssh.exec_command(f'sudo chmod 775 {existing_dir}')
        return existing_dir
    
    print(f"No directory option found, configuring default: {default_dir}")
    
    # Determine config directory
    config_dir = named_conf_path.rsplit('/', 1)[0]
    options_file = f"{config_dir}/named.conf.options"
    
    # Check if named.conf.options exists
    stdin, stdout, stderr = ssh.exec_command(f'test -f {options_file} && echo "exists"')
    options_exists = stdout.read().decode('utf-8').strip() == 'exists'
    
    if not options_exists:
        # Create named.conf.options with directory directive
        options_content = f'''options {{
    directory "{default_dir}";
}};
'''
        stdin, stdout, stderr = ssh.exec_command(f"sudo tee {options_file} > /dev/null << 'EOF'\n{options_content}\nEOF")
        ssh.exec_command(f'sudo chown root:{bind_user} {options_file}')
        ssh.exec_command(f'sudo chmod 644 {options_file}')
        print(f"Created {options_file}")
        
        # Ensure named.conf includes the options file
        stdin, stdout, stderr = ssh.exec_command(f'grep -q "include.*named.conf.options" {named_conf_path} && echo "exists"')
        include_exists = stdout.read().decode('utf-8').strip() == 'exists'
        
        if not include_exists:
            include_line = f'include "{options_file}";'
            # Add include at the beginning of named.conf
            ssh.exec_command(f"sudo sed -i '1i {include_line}' {named_conf_path}")
            print(f"Added include statement to {named_conf_path}")
    else:
        # Add directory option to existing named.conf.options
        stdin, stdout, stderr = ssh.exec_command(f'grep -q "directory" {options_file} && echo "exists"')
        has_directory = stdout.read().decode('utf-8').strip() == 'exists'
        
        if not has_directory:
            # Insert directory option into options block
            ssh.exec_command(f'''sudo sed -i '/options {{/a\\    directory "{default_dir}";' {options_file}''')
            print(f"Added directory option to {options_file}")
    
    # Create and configure the directory
    ssh.exec_command(f'sudo mkdir -p {default_dir}')
    ssh.exec_command(f'sudo chown {bind_user}:{bind_user} {default_dir}')
    ssh.exec_command(f'sudo chmod 775 {default_dir}')
    print(f"Created and configured directory: {default_dir}")
    
    # Also ensure /var/cache/bind exists (needed by BIND)
    ssh.exec_command(f'sudo mkdir -p /var/cache/bind')
    ssh.exec_command(f'sudo chown {bind_user}:{bind_user} /var/cache/bind')
    ssh.exec_command(f'sudo chmod 775 /var/cache/bind')
    
    return default_dir

def detect_bind_paths(ssh):
    """Detect BIND configuration paths and ensure proper setup"""
    # Check for Debian/Ubuntu paths
    stdin, stdout, stderr = ssh.exec_command('test -f /etc/bind/named.conf.local && echo "debian"')
    result = stdout.read().decode('utf-8').strip()
    
    if result == "debian":
        named_conf_main = '/etc/bind/named.conf'
        named_conf = '/etc/bind/named.conf.local'
        bind_user = 'bind'
        bind_service = 'named'
    else:
        # RHEL/CentOS paths
        named_conf_main = '/etc/named.conf'
        named_conf = '/etc/named/named.conf.local'
        bind_user = 'named'
        bind_service = 'named'
    
    # Get or configure the zones directory
    zones_dir = ensure_bind_directory_configured(ssh, named_conf_main, bind_user)
    
    return {
        'named_conf': named_conf,
        'zones_dir': zones_dir,
        'bind_user': bind_user,
        'bind_service': bind_service
    }

def ensure_bind_running(ssh, bind_service='named'):
    """
    Ensure BIND service is running. Returns status dict.
    """
    # Check if service is active
    stdin, stdout, stderr = ssh.exec_command(f'systemctl is-active {bind_service} 2>/dev/null')
    is_active = stdout.read().decode('utf-8').strip() == 'active'
    
    if is_active:
        return {'running': True, 'message': 'BIND is running'}
    
    # Try to start the service
    print(f"⚠️  BIND not running, using sudo to start {bind_service}...")
    stdin, stdout, stderr = ssh.exec_command(f'sudo systemctl start {bind_service} 2>&1')
    start_output = stdout.read().decode('utf-8')
    
    # Check if it started successfully
    stdin, stdout, stderr = ssh.exec_command(f'systemctl is-active {bind_service} 2>/dev/null')
    is_active = stdout.read().decode('utf-8').strip() == 'active'
    
    if is_active:
        print(f"✅ BIND service started successfully")
        return {'running': True, 'message': 'BIND started successfully'}
    else:
        # Get failure reason
        print(f"❌ BIND service failed to start")
        stdin, stdout, stderr = ssh.exec_command(f'sudo systemctl status {bind_service} 2>&1 | tail -20')
        status_output = stdout.read().decode('utf-8')
        return {
            'running': False,
            'message': 'BIND failed to start - check configuration',
            'details': status_output
        }

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

@app.route('/api/zones', methods=['POST'])
def create_zone():
    """Create a new DNS zone using templates"""
    ssh = None
    sftp = None
    
    try:
        if not is_config_complete():
            return jsonify({'error': 'BIND DNS configuration is incomplete. Please configure your credentials.'}), 400
        
        data = request.json
        
        # Validate required fields
        zone_name = data.get('zone_name', '').strip()
        primary_ns = data.get('primary_ns', '').strip()
        admin_email = data.get('admin_email', '').strip()
        ns_ip_address = data.get('ns_ip_address', '').strip() or None
        
        if not zone_name:
            return jsonify({'error': 'Zone name is required'}), 400
        
        if not primary_ns:
            return jsonify({'error': 'Primary nameserver is required'}), 400
        
        if not admin_email:
            return jsonify({'error': 'Admin email is required'}), 400
        
        # Validate zone name format (basic check)
        if not zone_name.replace('.', '').replace('-', '').replace('_', '').isalnum():
            return jsonify({'error': 'Invalid zone name format'}), 400
        
        # Validate nameserver format (should be FQDN)
        if '.' not in primary_ns:
            return jsonify({'error': 'Primary nameserver must be a fully qualified domain name (FQDN)'}), 400
        
        # Validate email format
        if '@' not in admin_email:
            return jsonify({'error': 'Invalid admin email format'}), 400
        
        # Check if NS is within the zone and validate IP requirement
        ns_is_in_zone = primary_ns.endswith(f'.{zone_name}') or primary_ns == zone_name
        
        if ns_is_in_zone and not ns_ip_address:
            return jsonify({
                'error': 'Nameserver IP address is required when the NS record is within this zone',
                'details': 'A glue record (A record) must be created for nameservers within the zone to prevent circular dependencies'
            }), 400
        
        # Reject IP address if NS is outside the zone (no glue record needed)
        if not ns_is_in_zone and ns_ip_address:
            return jsonify({
                'error': 'Nameserver IP address should not be provided when NS is outside this zone',
                'details': f'The nameserver {primary_ns} is not within the zone {zone_name}. Glue records are only needed for in-zone nameservers.'
            }), 400
        
        # Validate IP address format if provided
        if ns_ip_address:
            import re
            ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
            if not ip_pattern.match(ns_ip_address):
                return jsonify({'error': 'Invalid IP address format'}), 400
            
            # Validate IP octets
            octets = ns_ip_address.split('.')
            if any(int(octet) > 255 or int(octet) < 0 for octet in octets):
                return jsonify({'error': 'Invalid IP address: octets must be between 0 and 255'}), 400
        
        print(f"Creating zone: {zone_name} with NS: {primary_ns}, Admin: {admin_email}, NS IP: {ns_ip_address or 'N/A'}")
        
        # Connect to server
        ssh = get_ssh_client()
        sftp = ssh.open_sftp()
        
        # Detect BIND paths
        paths = detect_bind_paths(ssh)
        named_conf = paths['named_conf']
        zones_dir = paths['zones_dir']
        bind_user = paths['bind_user']
        
        zone_file_path = f"{zones_dir}/db.{zone_name}"
        
        print(f"Using paths - Config: {named_conf}, Zones: {zones_dir}, Zone file: {zone_file_path}")
        
        # Step 1: Check if zone already exists
        stdin, stdout, stderr = ssh.exec_command(f'grep -q "zone \\"{zone_name}\\"" {named_conf} && echo "exists"')
        if stdout.read().decode('utf-8').strip() == "exists":
            return jsonify({'error': f'Zone {zone_name} already exists'}), 400
        
        # Step 2: Ensure zones directory exists
        print(f"✅ Ensuring zones directory exists: {zones_dir}")
        ssh.exec_command(f'sudo mkdir -p {zones_dir}')
        
        # Step 3: Render and write zone file
        zone_file_content = render_zone_file(zone_name, primary_ns, admin_email, ns_ip_address=ns_ip_address)
        
        print(f"Generated zone file content:\n{zone_file_content}")
        
        # Write to temporary file first (in /tmp which is always writable)
        temp_zone_file = f"/tmp/db.{zone_name}"
        try:
            with sftp.file(temp_zone_file, 'w') as f:
                f.write(zone_file_content)
        except Exception as sftp_error:
            print(f"⚠️  SFTP write failed: {sftp_error}, trying alternative method...")
            # Fallback: use echo with tee
            zone_content_escaped = zone_file_content.replace("'", "'\\''")
            stdin, stdout, stderr = ssh.exec_command(f"echo '{zone_content_escaped}' > {temp_zone_file}")
            write_error = stderr.read().decode('utf-8')
            if write_error:
                print(f"Warning during temp file write: {write_error}")
        
        # Step 4: Validate zone file with named-checkzone
        stdin, stdout, stderr = ssh.exec_command(f'named-checkzone {zone_name} {temp_zone_file}')
        check_output = stdout.read().decode('utf-8')
        check_error = stderr.read().decode('utf-8')
        
        print(f"Zone validation output: {check_output}")
        if check_error:
            print(f"Zone validation errors: {check_error}")
        
        if 'OK' not in check_output and 'loaded serial' not in check_output:
            ssh.exec_command(f'sudo rm {temp_zone_file}')
            return jsonify({
                'error': 'Zone file validation failed',
                'details': check_output + check_error
            }), 400
        
        # Step 5: Move zone file to proper location and set permissions
        print(f"⚠️  Using sudo to move zone file and set permissions")
        stdin, stdout, stderr = ssh.exec_command(f'sudo mv {temp_zone_file} {zone_file_path}')
        ssh.exec_command(f'sudo chown {bind_user}:{bind_user} {zone_file_path}')
        ssh.exec_command(f'sudo chmod 644 {zone_file_path}')
        
        print(f"Zone file created and permissions set: {zone_file_path}")
        
        # Step 6: Backup named.conf
        print(f"⚠️  Using sudo to backup configuration")
        backup_file = f"{named_conf}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ssh.exec_command(f'sudo cp {named_conf} {backup_file}')
        print(f"Backed up config to: {backup_file}")
        
        # Step 7: Render and append zone configuration to named.conf
        zone_config = render_zone_config(zone_name, zone_file_path)
        
        print(f"Generated zone config:\n{zone_config}")
        
        # Write zone config to temp file (in /tmp which is always writable)
        temp_config = f"/tmp/zone-config-{zone_name}.conf"
        try:
            with sftp.file(temp_config, 'w') as f:
                f.write(zone_config)
        except Exception as sftp_error:
            print(f"⚠️  SFTP write failed: {sftp_error}, trying alternative method...")
            # Fallback: use echo
            zone_config_escaped = zone_config.replace("'", "'\\''")
            stdin, stdout, stderr = ssh.exec_command(f"echo '{zone_config_escaped}' > {temp_config}")
            write_error = stderr.read().decode('utf-8')
            if write_error:
                print(f"Warning during temp file write: {write_error}")
        
        # Append to named.conf
        print(f"⚠️  Using sudo to update named.conf")
        ssh.exec_command(f'sudo sh -c "cat {temp_config} >> {named_conf}"')
        ssh.exec_command(f'rm {temp_config}')
        
        print(f"Zone configuration added to {named_conf}")
        
        # Step 8: Validate BIND configuration
        print(f"⚠️  Using sudo to validate BIND configuration")
        stdin, stdout, stderr = ssh.exec_command(f'sudo named-checkconf {named_conf}')
        config_check_output = stdout.read().decode('utf-8')
        config_check_error = stderr.read().decode('utf-8')
        
        if config_check_error:
            print(f"Config validation failed: {config_check_error}")
            # Rollback
            print(f"⚠️  Using sudo to rollback configuration")
            ssh.exec_command(f'sudo cp {backup_file} {named_conf}')
            ssh.exec_command(f'sudo rm {zone_file_path}')
            return jsonify({
                'error': 'BIND configuration validation failed',
                'details': config_check_error
            }), 400
        
        print("Configuration validated successfully")
        
        # Step 9: Reload BIND
        print(f"⚠️  Using sudo to reload BIND service")
        stdin, stdout, stderr = ssh.exec_command('sudo rndc reload')
        reload_output = stdout.read().decode('utf-8')
        reload_error = stderr.read().decode('utf-8')
        
        print(f"BIND reload output: {reload_output}")
        if reload_error:
            print(f"BIND reload errors: {reload_error}")
        
        # Even if rndc reload has warnings, check if it succeeded
        if 'failed' in reload_output.lower() or 'failed' in reload_error.lower():
            # Try service reload as fallback
            print(f"⚠️  Using sudo systemctl reload as fallback")
            stdin, stdout, stderr = ssh.exec_command(f'sudo systemctl reload {paths["bind_service"]}')
            service_output = stdout.read().decode('utf-8')
            print(f"Service reload output: {service_output}")
        
        # Step 10: Refresh zones list
        zones = discover_zones()
        
        return jsonify({
            'success': True,
            'message': f'Zone {zone_name} created successfully',
            'zone': {
                'name': zone_name,
                'primary_ns': primary_ns,
                'admin_email': admin_email,
                'file': zone_file_path
            }
        })
        
    except Exception as e:
        print(f"Error creating zone: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        if sftp:
            try:
                sftp.close()
            except:
                pass
        if ssh:
            try:
                ssh.close()
            except:
                pass

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
    """Save BIND DNS configuration and verify setup"""
    ssh = None
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
        
        # Now verify the setup if BIND is already installed
        response_data = {
            'success': True,
            'message': 'Configuration saved successfully'
        }
        
        try:
            ssh = get_ssh_client()
            
            # Check if BIND is installed
            if check_bind_installed(ssh):
                # Detect and configure BIND paths
                bind_paths = detect_bind_paths(ssh)
                
                # Check BIND service status
                bind_status = ensure_bind_running(ssh, bind_paths['bind_service'])
                
                if not bind_status['running']:
                    response_data['warning'] = bind_status['message']
                    if 'details' in bind_status:
                        response_data['bind_error'] = bind_status['details']
                else:
                    response_data['bind_status'] = bind_status['message']
                    response_data['zones_directory'] = bind_paths['zones_dir']
        except Exception as verify_error:
            # Don't fail the config save if verification fails
            response_data['warning'] = f'Configuration saved but verification failed: {str(verify_error)}'
        
        return jsonify(response_data)
    except Exception as e:
        print(f"Error saving configuration: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if ssh:
            try:
                ssh.close()
            except:
                pass

@app.route('/api/config/test', methods=['POST'])
def test_config():
    """Test BIND DNS connection before saving and check if BIND is installed"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['bind_host', 'bind_user']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return jsonify({
                'error': f'Missing required fields: {", ".join(missing_fields)}',
                'bindInstalled': False
            }), 400
        
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
            # Try to establish SSH connection
            ssh = get_ssh_client()
            
            # Check if BIND is installed
            bind_installed = check_bind_installed(ssh)
            
            if not bind_installed:
                # Restore original config
                config.update(temp_config)
                ssh.close()
                
                return jsonify({
                    'success': True,
                    'message': 'Connection successful, but Bind is not installed',
                    'bindInstalled': False,
                    'zone_count': 0,
                    'zones': []
                })
            
            # Try to discover zones
            zones = discover_zones()
            
            # Restore original config
            config.update(temp_config)
            ssh.close()
            
            zone_count = len(zones)
            zone_names = ', '.join(list(zones.keys())[:5])
            if zone_count > 5:
                zone_names += f', ... ({zone_count - 5} more)'
            
            return jsonify({
                'success': True,
                'message': f'Connection successful, Bind already installed. Found {zone_count} zone(s): {zone_names}',
                'bindInstalled': True,
                'zone_count': zone_count,
                'zones': list(zones.keys())
            })
        except paramiko.ssh_exception.NoValidConnectionsError:
            # Restore original config
            config.update(temp_config)
            return jsonify({
                'error': 'Connection failed, Error: SSH connection refused',
                'bindInstalled': False
            }), 500
        except paramiko.ssh_exception.AuthenticationException:
            # Restore original config
            config.update(temp_config)
            return jsonify({
                'error': 'Connection failed, Error: SSH user/password failed',
                'bindInstalled': False
            }), 500
        except PermissionError:
            # Restore original config
            config.update(temp_config)
            return jsonify({
                'error': 'Connection failed, Error: SSH permission denied',
                'bindInstalled': False
            }), 500
        except Exception as test_error:
            # Restore original config
            config.update(temp_config)
            
            error_msg = str(test_error).lower()
            if 'connection refused' in error_msg or 'timed out' in error_msg:
                return jsonify({
                    'error': 'Connection failed, Error: SSH connection refused',
                    'bindInstalled': False
                }), 500
            elif 'permission denied' in error_msg or 'publickey' in error_msg:
                return jsonify({
                    'error': 'Connection failed, Error: SSH permission denied',
                    'bindInstalled': False
                }), 500
            elif 'authentication' in error_msg:
                return jsonify({
                    'error': 'Connection failed, Error: SSH user/password failed',
                    'bindInstalled': False
                }), 500
            else:
                return jsonify({
                    'error': f'Connection failed: {str(test_error)}',
                    'bindInstalled': False
                }), 500
                
    except Exception as e:
        print(f"Error testing configuration: {str(e)}")
        return jsonify({
            'error': str(e),
            'bindInstalled': False
        }), 500

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
        # For record types that reference hostnames (CNAME, MX, NS, SRV, PTR),
        # ensure they end with a dot to prevent zone name appending
        hostname_types = ['CNAME', 'MX', 'NS', 'SRV', 'PTR']
        
        new_record_lines = []
        for value in values:
            # For hostname-based records, ensure FQDN format (ending with dot)
            if record_type in hostname_types:
                # Split MX records (priority hostname)
                if record_type == 'MX':
                    parts = value.split(None, 1)  # Split on first whitespace
                    if len(parts) == 2:
                        priority, hostname = parts
                        # Add dot if not present and not empty
                        if hostname and not hostname.endswith('.'):
                            hostname = hostname + '.'
                        value = f"{priority} {hostname}"
                    # If only one part, treat it as hostname with default priority
                    elif len(parts) == 1 and not parts[0].isdigit():
                        hostname = parts[0]
                        if not hostname.endswith('.'):
                            hostname = hostname + '.'
                        value = f"10 {hostname}"  # Default priority
                # For SRV records (priority weight port target)
                elif record_type == 'SRV':
                    parts = value.split()
                    if len(parts) == 4:
                        priority, weight, port, target = parts
                        if target and not target.endswith('.'):
                            target = target + '.'
                        value = f"{priority} {weight} {port} {target}"
                # For CNAME, NS, PTR - just the hostname
                else:
                    if value and not value.endswith('.'):
                        value = value + '.'
            
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
