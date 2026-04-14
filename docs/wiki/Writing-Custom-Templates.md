# Writing Custom Templates

Conpot templates define the device personality your honeypot presents to the network. A well-crafted template makes the difference between catching a Shodan indexer and catching a targeted adversary who believes they're talking to a real PLC.

## Template Structure

A Conpot template is a directory containing XML configuration files for each emulated protocol:

```
my-template/
  template.xml          # Main template — device identity, protocol bindings
  s7comm/
    s7comm.xml          # S7comm protocol responses (SZL data, module info)
  modbus/
    modbus.xml          # Modbus register map and device identification
  bacnet/
    bacnet.xml          # BACnet object list and property values
  snmp/
    snmp.xml            # SNMP MIB values
  http/
    template.html       # HMI web interface
    style.css
```

## Principles of Realistic Templates

### 1. Match Real Device Fingerprints

Scanning tools like Nmap, PLCScan, and Metasploit ICS modules fingerprint devices by their protocol responses. Your template should return values that match a real device.

**S7comm example** — an S7-300 PLC should return correct System Status List (SZL) data:
- Module type string (e.g., `6ES7 315-2EH14-0AB0`)
- Firmware version
- Serial number format
- Module order numbers

Research the specific device you're emulating. Siemens publishes order number catalogs. Use consistent values across protocols — if your S7 says it's a CPU 315-2 PN/DP, your HTTP HMI should reference the same model.

### 2. Populate Realistic Register Values

Empty Modbus registers are a dead giveaway. Real PLCs have:
- Holding registers with process values (temperatures, pressures, flow rates)
- Coils in mixed on/off states
- Input registers that change over time

Consider what the emulated device would be controlling and populate registers accordingly. A water treatment facility PLC might have:
- Register 0-9: Flow rates (realistic range: 50-200 GPM)
- Register 10-19: Chemical dosing levels
- Register 20-29: Tank levels (0-100%)

### 3. Consistent Device Identity

Every protocol should tell the same story:
- **S7comm SZL** → Siemens S7-315
- **Modbus device ID** → Siemens, product code matching the S7 model
- **SNMP sysDescr** → Siemens SIMATIC S7-300
- **HTTP banner** → Siemens HMI portal for S7-300
- **BACnet device object** → Consistent vendor/model strings

Inconsistencies are how researchers and sophisticated attackers detect honeypots.

### 4. HMI Web Interface

The HTTP template (`template.html`) is often the first thing a scanner sees. Tips:
- Use the vendor's actual CSS styling where possible (colors, fonts, layout)
- Include realistic navigation structure (diagnostics, configuration, status pages)
- Show plausible process data on the main page
- Don't leave default Conpot branding visible

## Testing Your Template

### Protocol-Level Testing

Use standard ICS tools to verify your template responds correctly:

```bash
# Modbus — read holding registers
modbus read -a 1 -t 4:0 -c 10 YOUR_HONEYPOT_IP

# S7comm — read device info
python3 -c "import snap7; c=snap7.client.Client(); c.connect('YOUR_IP',0,2); print(c.get_cpu_info())"

# BACnet — read device object
bacnet read YOUR_IP analogInput:0 presentValue

# SNMP — walk the MIB
snmpwalk -v2c -c public YOUR_IP
```

### Fingerprint Testing

Run the same tools attackers use to see if your honeypot passes:
```bash
nmap -sV -p 502,102 YOUR_HONEYPOT_IP
```

Compare the output against a scan of the real device (or published scan results) to check for discrepancies.

## Template Examples

Conpot ships with several built-in templates:
- `default` — generic ICS device
- `guardian_ast` — Veeder-Root Guardian AST (gas station tank gauge)
- `ipmi` — IPMI BMC

The [Conpot documentation](https://conpot.readthedocs.io/) has additional details on template XML schema and available protocol handlers.

## Contributing Templates

When contributing templates back to the project:
- Do not include proprietary firmware images or copyrighted material
- Document what device the template emulates and which protocols are configured
- Note any known fingerprinting gaps (e.g., "Nmap detects this as Conpot due to X")
- Test with at least Nmap and one ICS-specific tool before submitting
