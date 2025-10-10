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
    'DNS_ZONE': os.getenv('DNS_ZONE'),
    'ZONE_FILE_PATH': os.getenv('ZONE_FILE_PATH')
}

def is_config_complete():
    """Check if all required configuration is present"""
    required = ['BIND_HOST', 'BIND_USER', 'DNS_ZONE', 'ZONE_FILE_PATH']
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

def read_zone_file():
    """Read and parse the BIND zone file via SSH"""
    ssh = None
    try:
        ssh = get_ssh_client()
        
        # Read the zone file
        zone_path = config['ZONE_FILE_PATH']
        stdin, stdout, stderr = ssh.exec_command(f'cat {zone_path}')
        zone_data = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        if error and 'No such file' in error:
            raise Exception(f"Zone file not found: {zone_path}")
        
        if not zone_data:
            raise Exception(f"Zone file is empty or could not be read: {zone_path}")
        
        return zone_data
    finally:
        if ssh:
            ssh.close()

def parse_zone_data(zone_data):
    """Parse BIND zone file data and return structured records"""
    try:
        zone = dns.zone.from_text(zone_data, origin=config['DNS_ZONE'], check_origin=False)
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
                    fqdn = f"{name_str}.{config['DNS_ZONE']}" if name_str != '@' else config['DNS_ZONE']
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

def write_zone_file(zone_data):
    """Write updated zone file to BIND server via SSH"""
    ssh = None
    try:
        ssh = get_ssh_client()
        
        zone_path = config['ZONE_FILE_PATH']
        # Create a temporary file and write to it
        temp_path = f"{zone_path}.tmp"
        
        # Write zone data to temp file
        sftp = ssh.open_sftp()
        with sftp.file(temp_path, 'w') as f:
            f.write(zone_data)
        sftp.close()
        
        # Validate the zone file with named-checkzone
        zone_name = config['DNS_ZONE']
        stdin, stdout, stderr = ssh.exec_command(f'named-checkzone {zone_name} {temp_path}')
        check_output = stdout.read().decode('utf-8')
        check_error = stderr.read().decode('utf-8')
        
        if 'OK' not in check_output:
            ssh.exec_command(f'rm {temp_path}')
            raise Exception(f"Zone file validation failed: {check_error}")
        
        # Move temp file to actual zone file
        ssh.exec_command(f'mv {temp_path} {zone_path}')
        
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
    return jsonify({'status': 'healthy', 'zone': config.get('DNS_ZONE')})

@app.route('/api/config/status', methods=['GET'])
def config_status():
    """Check if BIND DNS configuration is complete"""
    try:
        complete = is_config_complete()
        return jsonify({
            'configured': complete,
            'zone': config.get('DNS_ZONE') if complete else None
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
            'dns_zone': config.get('DNS_ZONE', ''),
            'zone_file_path': config.get('ZONE_FILE_PATH', ''),
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
        required_fields = ['bind_host', 'bind_user', 'dns_zone', 'zone_file_path']
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
            'DNS_ZONE': data['dns_zone'],
            'ZONE_FILE_PATH': data['zone_file_path']
        }
        
        if data.get('bind_ssh_key'):
            new_config['BIND_SSH_KEY'] = data['bind_ssh_key']
        if data.get('bind_password'):
            new_config['BIND_PASSWORD'] = data['bind_password']
        
        update_config(new_config)
        
        return jsonify({
            'success': True,
            'message': 'Configuration saved successfully',
            'zone': config['DNS_ZONE']
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
        required_fields = ['bind_host', 'bind_user', 'dns_zone', 'zone_file_path']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
        
        # Temporarily update config for testing
        temp_config = config.copy()
        config.update({
            'BIND_HOST': data['bind_host'],
            'BIND_PORT': data.get('bind_port', '22'),
            'BIND_USER': data['bind_user'],
            'DNS_ZONE': data['dns_zone'],
            'ZONE_FILE_PATH': data['zone_file_path'],
            'BIND_SSH_KEY': data.get('bind_ssh_key'),
            'BIND_PASSWORD': data.get('bind_password')
        })
        
        try:
            # Try to read the zone file
            zone_data = read_zone_file()
            records = parse_zone_data(zone_data)
            
            # Restore original config
            config.update(temp_config)
            
            return jsonify({
                'success': True,
                'message': f'Connection successful! Found {len(records)} DNS records.',
                'record_count': len(records),
                'zone': data['dns_zone']
            })
        except Exception as test_error:
            # Restore original config
            config.update(temp_config)
            
            error_msg = str(test_error)
            if 'Authentication failed' in error_msg or 'No authentication' in error_msg:
                return jsonify({'error': 'Authentication failed. Please check your credentials.'}), 401
            elif 'Connection refused' in error_msg or 'timed out' in error_msg:
                return jsonify({'error': f'Cannot connect to {data["bind_host"]}. Check host and port.'}), 500
            elif 'Zone file not found' in error_msg:
                return jsonify({'error': f'Zone file not found: {data["zone_file_path"]}'}), 404
            else:
                return jsonify({'error': f'Connection failed: {error_msg}'}), 500
                
    except Exception as e:
        print(f"Error testing configuration: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/records', methods=['GET'])
def get_records():
    """Get all DNS records from the BIND zone"""
    try:
        # Check if configuration is complete
        if not is_config_complete():
            return jsonify({'error': 'BIND DNS configuration is incomplete. Please configure your credentials.'}), 400
        
        print(f"Attempting to read BIND DNS Zone: {config['DNS_ZONE']}")
        
        # Read and parse zone file
        zone_data = read_zone_file()
        records = parse_zone_data(zone_data)
        
        print(f"Successfully retrieved {len(records)} records")
        return jsonify({'records': records, 'zone': config['DNS_ZONE']})
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
        record_name = data.get('name')
        record_type = data.get('type')
        ttl = data.get('ttl', 3600)
        values = data.get('values', [])
        
        if not record_name or not record_type or not values:
            return jsonify({'error': 'Missing required fields: name, type, values'}), 400
        
        if not is_config_complete():
            return jsonify({'error': 'BIND DNS configuration is incomplete.'}), 400
        
        # Read current zone file
        zone_data = read_zone_file()
        
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
        write_zone_file(updated_zone)
        
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
    required_vars = ['BIND_HOST', 'BIND_USER', 'DNS_ZONE', 'ZONE_FILE_PATH']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"WARNING: Missing environment variables: {', '.join(missing_vars)}")
        print("The application will start, but you need to configure BIND DNS credentials in Settings.")
        print(f"Starting BIND DNS Manager (unconfigured)")
    else:
        print(f"Starting BIND DNS Manager for zone: {config['DNS_ZONE']}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
