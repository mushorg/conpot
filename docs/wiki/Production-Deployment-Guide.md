# Production Deployment Guide

This guide covers deploying Conpot in a production honeypot environment using rootless Podman with security hardening. While Conpot can be run directly via `pip install`, containerized deployment provides better isolation — especially important when capturing live attacker traffic.

## Architecture Overview

A typical ICS honeypot deployment consists of:

- **Conpot container** — emulates ICS protocols (Modbus, S7comm, BACnet, SNMP, HTTP/HMI)
- **Log ingestion pipeline** — tails Conpot JSON logs and stores events in a database
- **Firewall zones** — separates honeypot-facing traffic from management access

```
Internet --> [Firewall] --> Honeypot Zone (ICS ports) --> Conpot Container
                        --> Management Zone (SSH, dashboard) --> Admin only
```

## Prerequisites

- Linux host (RHEL/Fedora/Rocky recommended for SELinux support)
- Podman (rootless)
- A dedicated non-root user (e.g., `honeypot`)
- firewalld with zone support

## Step 1: Create a Dedicated User

```bash
sudo useradd -r -m -s /bin/bash honeypot
sudo loginctl enable-linger honeypot   # allows rootless containers to persist
```

## Step 2: Directory Structure

```bash
sudo -u honeypot mkdir -p /home/honeypot/honeypot/{templates,config,conpot-logs,data}
```

- `templates/` — custom Conpot templates (device profiles)
- `config/` — `conpot.cfg` configuration
- `conpot-logs/` — bind-mounted log directory for ingestion
- `data/` — database and enrichment data

## Step 3: Run Conpot with Security Hardening

```bash
sudo -u honeypot bash -c 'export XDG_RUNTIME_DIR=/run/user/$(id -u) && \
podman run -d \
  --name conpot \
  --restart=always \
  --read-only \
  --cap-drop=ALL \
  --cap-add=NET_BIND_SERVICE \
  --security-opt=no-new-privileges \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  -v /home/honeypot/honeypot/templates/my-template:/path/to/conpot/templates/my-template:ro \
  -v /home/honeypot/honeypot/conpot-logs:/var/log/conpot:rw \
  -v /home/honeypot/honeypot/config/conpot.cfg:/etc/conpot/conpot.cfg:ro \
  -p 80:80/tcp \
  -p 102:102/tcp \
  -p 502:502/tcp \
  -p 161:161/udp \
  docker.io/honeynet/conpot:latest \
  /usr/bin/python3 /home/conpot/.local/bin/conpot \
    --template my-template \
    -c /etc/conpot/conpot.cfg \
    -f --logfile /var/log/conpot/conpot.log \
    --temp_dir /tmp'
```

### What the Security Flags Do

| Flag | Purpose |
|------|---------|
| `--read-only` | Container filesystem is immutable — attacker can't write to it |
| `--cap-drop=ALL` | Strips all Linux capabilities |
| `--cap-add=NET_BIND_SERVICE` | Only adds back the ability to bind low ports |
| `--security-opt=no-new-privileges` | Prevents privilege escalation via setuid binaries |
| `--tmpfs /tmp:noexec,nosuid` | Writable temp space, but nothing can be executed from it |
| `:ro` volume mounts | Templates and config are read-only inside the container |

## Step 4: Firewall Zone Isolation

Create a dedicated firewall zone that only exposes honeypot ports to the internet, and a separate management zone restricted to your admin IPs.

```bash
# Create honeypot zone — accepts only ICS traffic
sudo firewall-cmd --permanent --new-zone=ics-honeypot
sudo firewall-cmd --permanent --zone=ics-honeypot --set-target=ACCEPT
sudo firewall-cmd --permanent --zone=ics-honeypot --add-port=502/tcp    # Modbus
sudo firewall-cmd --permanent --zone=ics-honeypot --add-port=102/tcp    # S7comm
sudo firewall-cmd --permanent --zone=ics-honeypot --add-port=47808/udp  # BACnet
sudo firewall-cmd --permanent --zone=ics-honeypot --add-port=80/tcp     # HTTP/HMI
sudo firewall-cmd --permanent --zone=ics-honeypot --add-port=161/udp    # SNMP

# Assign your external interface
sudo firewall-cmd --permanent --zone=ics-honeypot --change-interface=eno1

# Create management zone — restricted to admin IPs
sudo firewall-cmd --permanent --new-zone=management
sudo firewall-cmd --permanent --zone=management --add-source=YOUR.ADMIN.IP/32
sudo firewall-cmd --permanent --zone=management --add-port=22222/tcp    # Real SSH (non-standard port)
sudo firewall-cmd --permanent --zone=management --add-port=8888/tcp     # Dashboard

# Default zone drops everything
sudo firewall-cmd --set-default-zone=drop
sudo firewall-cmd --reload
```

**Key principle:** The honeypot ports are open to the world, but management access (real SSH, dashboards) is only reachable from specific admin IPs. An attacker interacting with Conpot has no path to your management services.

## Step 5: SELinux

Ensure SELinux is enforcing. Rootless Podman containers automatically get proper SELinux labels (`container_t` process label, `container_file_t` for volumes).

```bash
getenforce          # should say "Enforcing"
sudo semanage port -a -t ssh_port_t -p tcp 22222   # if using non-standard SSH port
```

Do **not** disable SELinux. It is your strongest containment layer against container escape.

## Step 6: Audit Rules for Container Escape Detection

Add audit rules to detect container breakout attempts:

```bash
cat << 'EOF' | sudo tee /etc/audit/rules.d/honeypot.rules
# Namespace manipulation (container escape indicator)
-a always,exit -F arch=b64 -S unshare -S setns -k container_escape

# Mount/umount (filesystem breakout)
-a always,exit -F arch=b64 -S mount -S umount2 -F auid>=1000 -k container_mount

# Ptrace (process injection)
-a always,exit -F arch=b64 -S ptrace -k container_ptrace

# Kernel module loading (rootkit indicator)
-a always,exit -F arch=b64 -S init_module -S finit_module -S delete_module -k kernel_module

# Honeypot user SSH key tampering
-w /home/honeypot/.ssh/ -p wa -k honeypot_ssh

# Container runtime config changes
-w /home/honeypot/.config/containers/ -p wa -k container_config
EOF

sudo augenrules --load
```

Check for suspicious events with:
```bash
sudo ausearch -k container_escape --start recent
```

## Step 7: Health Monitoring

A simple health check script that verifies ports are listening:

```bash
#!/bin/bash
# /usr/local/bin/honeypot-health.sh
for port in 502 102 80 161; do
    if ! ss -tln | grep -q ":${port} "; then
        echo "ALERT: port $port down" | logger -t honeypot-health
    fi
done
```

Run via systemd timer or cron every 2-5 minutes.

## Step 8: Log Rotation

Conpot logs can grow quickly under heavy scanning. Configure rotation:

```
# /etc/logrotate.d/conpot
/home/honeypot/honeypot/conpot-logs/*.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
    copytruncate
}
```

**Note:** If you have a log watcher tailing Conpot's JSON output, be aware that log rotation can cause the watcher to lose its file handle. Use `copytruncate` (truncates in place rather than renaming) or implement rotation-aware watching with inotify `CREATE` events.

## Common Issues

### Conpot exits immediately
Check that your template path inside the container matches the installed location. The path varies by Conpot version — inspect the image with `podman run --rm -it conpot:latest find / -name "templates" -type d`.

### Ports already in use
If another service is bound to port 502 or 102, Conpot will fail silently. Check with `ss -tlnp` before starting.

### No events in logs
Verify the log directory is writable by the container user. With rootless Podman, UID mapping can cause permission issues. Check `podman unshare ls -la /home/honeypot/honeypot/conpot-logs/`.

### Internal container IPs in logs
Rootless Podman uses an internal network (typically `10.89.0.0/24`). If you're ingesting logs into a database, filter out events where `source_ip` falls within RFC 1918 ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) to avoid counting internal traffic as attacks.
