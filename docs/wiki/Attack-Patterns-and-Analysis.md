# Attack Patterns and Analysis

This page documents common attack patterns observed against Conpot honeypots. Understanding what to expect helps operators distinguish noise from targeted activity.

## Traffic Tiers

Internet-facing honeypot traffic generally falls into three tiers:

### Tier 1: Internet Background Noise
- **SSH brute-force** — Mirai variants and credential-stuffing bots. Arrives within hours of deployment. Uses well-known default credential lists (`root/admin`, `root/123456`, `root/P`, `admin/admin`). Automated, high-volume, not ICS-aware.
- **HTTP scanning** — Web crawlers, vulnerability scanners, and bots probing for web application vulnerabilities. Will hit your HMI on port 80.
- **Generic port probes** — SYN scans from Shodan, Censys, ZoomEye, and similar internet-wide scanners. These index your open ports but don't send protocol-specific payloads.

**Expected timeline:** Minutes to hours after deployment.

### Tier 2: Protocol-Aware Scanning
- **Modbus device identification** — Function code 43 (Read Device Identification) or reads of holding registers 0-10. Often from researchers or scanning platforms cataloging ICS devices.
- **S7comm connection requests** — COTP connection setup followed by S7 communication setup. SZL reads (system info) are reconnaissance. Usually automated.
- **BACnet Who-Is broadcasts** — BACnet device discovery. Common from building automation scanners.
- **SNMP walks** — Full MIB walks using community string `public`. Used for device fingerprinting.

**Expected timeline:** Days to weeks. Depends on how quickly internet indexers discover your honeypot.

### Tier 3: Targeted Interaction
- **Modbus write commands** — Function codes 5 (Write Single Coil), 6 (Write Single Register), 15 (Write Multiple Coils), 16 (Write Multiple Registers). Someone attempting to alter device state. Rare and significant.
- **S7 PLC control** — CPU start/stop commands, program uploads/downloads, memory writes. Extremely rare against honeypots.
- **Repeated visits from the same source** — An IP that returns multiple times with increasingly specific queries is likely a human operator, not a bot.

**Expected timeline:** Weeks to months, if ever. This is the high-value data.

## SSH Attack Patterns

If you're running an SSH honeypot (e.g., Cowrie) alongside Conpot, you'll see significantly more activity:

### Common Credential Lists
Botnets use dictionaries derived from default credentials in IoT devices and ICS equipment:
- `root/root`, `root/admin`, `root/123456`, `root/password`
- `admin/admin`, `admin/1234`
- Device-specific: `root/P` (Mirai), `ubnt/ubnt`, `pi/raspberry`
- ICS-specific: `ADMIN/ADMIN`, `USER/USER` (some PLCs ship with these)

### Post-Authentication Behavior
When a honeypot accepts credentials, bots typically:
1. **Fingerprint** — `uname -a`, `cat /proc/cpuinfo`, `free -m`
2. **Kill competitors** — Kill processes belonging to other botnets
3. **Download payload** — `curl`/`wget` from a C2 server, sometimes with `/dev/tcp` fallback
4. **Establish persistence** — Inject SSH keys into `authorized_keys`, set immutable flag with `chattr +ai`
5. **Beacon** — Send confirmation back to C2 (e.g., echo a specific string)

### Distinguishing Bots from Humans
| Signal | Bot | Human |
|--------|-----|-------|
| Timing | Milliseconds between commands | Seconds to minutes |
| Credential rotation | Systematic dictionary | Few targeted guesses |
| Commands | Identical across sessions | Adapted to responses |
| Payload | Same binary every time | May compile on target |
| Sessions | Parallel, many at once | Sequential, one at a time |

## Analysis Tips

### Correlating with Threat Intelligence
Cross-reference source IPs against:
- **GreyNoise** — classifies IPs as benign scanners vs. malicious
- **AbuseIPDB** — community-reported malicious IPs
- **Shodan** — shows what services the attacker's IP exposes (often compromised devices themselves)
- **CISA advisories** — match observed TTPs against published ICS threat alerts

### Tracking Campaigns
Group related sessions by:
- SSH key fingerprint (same key = same operator)
- C2 server addresses in download commands
- Malware hash (SHA256 of captured binaries)
- Credential list overlap
- ASN clustering (multiple IPs from the same hosting provider)

### What to Report
If you observe Tier 3 activity (actual ICS manipulation attempts), consider:
- Reporting to CISA via their [incident reporting form](https://www.cisa.gov/report)
- Sharing IOCs (IPs, hashes, C2 domains) with the ICS-CERT community
- Contributing anonymized data to threat intelligence platforms
