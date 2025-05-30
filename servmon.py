# app.py
from flask import Flask, render_template, redirect, url_for
import subprocess
import os
import re
from datetime import datetime

# Paths to data files
DHCP_LEASES_FILE = '/var/lib/misc/dnsmasq.leases'
RADIUS_LOG_FILE = '/var/log/freeradius/radius.log'

app = Flask(__name__)
SERVICE_MAP = {
    'dnsmasq': 'dnsmasq',
    'freeradius': 'freeradius'
}

# Helpers

def get_service_status(name):
    # Use subprocess.run to capture output even if service is inactive
    proc = subprocess.run([
        'systemctl', 'is-active', name
    ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    status = proc.stdout.decode().strip()
    return status if status else 'unknown'

def toggle_service(name):
    status = get_service_status(name)
    action = 'stop' if status == 'active' else 'start'
    subprocess.call(['sudo', 'systemctl', action, name])


def parse_dhcp_leases():
    leases = []
    if os.path.isfile(DHCP_LEASES_FILE):
        with open(DHCP_LEASES_FILE) as f:
            for line in f:
                parts = line.split()
                # dnsmasq.leases format: <expiry> <mac> <ip> <hostname> <client-id>
                if len(parts) >= 4:
                    expiry = int(parts[0])
                    mac = parts[1]
                    ip = parts[2]
                    hostname = parts[3]
                    # Convert expiry epoch to human-readable time
                    timestamp = datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M:%S')
                    leases.append({'time': timestamp, 'mac': mac, 'ip': ip, 'hostname': hostname})
    return leases[-20:][::-1]


def parse_radius_log():
    entries = []
    pattern = re.compile(r'Auth: \(\d+\)\s+(Login OK|Login Failed|Login incorrect): \[([^\]]+)\] \(from client (\S+)')
    if os.path.isfile(RADIUS_LOG_FILE):
        with open(RADIUS_LOG_FILE) as f:
            lines = f.readlines()[-100:]
            for line in lines:
                match = pattern.search(line)
                if match:
                    # Extract the timestamp portion before ': Auth'
                    raw_time = line.split(': Auth')[0].strip()
                    status_text = match.group(1)
                    user = match.group(2)
                    nas = match.group(3)
                    result = 'success' if 'OK' in status_text else 'failure'
                    entries.append({'time': raw_time, 'user': user, 'nas': nas, 'result': result})
    return entries[::-1]

# Routes

@app.route('/')
def index():
    dhcp_status = get_service_status(SERVICE_MAP['dnsmasq'])
    rad_status = get_service_status(SERVICE_MAP['freeradius'])
    leases = parse_dhcp_leases()
    rad_entries = parse_radius_log()

    return render_template('index.html',
                           dhcp_status=dhcp_status,
                           rad_status=rad_status,
                           leases=leases,
                           rad_entries=rad_entries)

@app.route('/toggle/<svc>')
def toggle(svc):
    if svc in SERVICE_MAP:
        toggle_service(SERVICE_MAP[svc])
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
