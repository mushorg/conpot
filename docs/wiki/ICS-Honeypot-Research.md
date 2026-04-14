# ICS Honeypot Research

A curated list of published research on ICS/SCADA honeypots, including papers that use or reference Conpot.

## Foundational Papers

- **Serbanescu, A. V., et al.** (2015). *ICS Threat Analysis Using a Large-Scale Honeynet.* — Early large-scale study using Conpot deployments across multiple countries to analyze ICS-targeted scanning patterns.

- **Antrobus, R., et al.** (2019). *The Forgotten I in IIoT: A Vulnerability Scanner for Industrial Internet of Things.* IEEE International Symposium on Software Reliability Engineering. — Demonstrates how ICS honeypots can be fingerprinted and proposes improvements.

- **Jicha, A., et al.** (2016). *SCADA Honeypots: An In-Depth Analysis of Conpot.* IEEE Conference on Communications and Network Security. — Detailed analysis of Conpot's protocol emulation fidelity and detection vectors.

## Honeypot Design and Evasion

- **Vetterl, A. & Clayton, R.** (2018). *Bitter Harvest: Systematically Fingerprinting Low- and Medium-Interaction Honeypots at Internet Scale.* USENIX Workshop on Offensive Technologies (WOOT). — Demonstrates fingerprinting of Conpot and other honeypots via protocol response analysis. Essential reading for improving template realism.

- **Zamiri-Gourabi, M., et al.** (2019). *Gas What? Revisiting and Improving the Classification of ICS Honeypots.* — Evaluates classification techniques for distinguishing real ICS devices from honeypots.

## Threat Landscape Studies

- **Mirian, A., et al.** (2016). *An Internet-Wide View of ICS Devices.* IEEE International Conference on Privacy, Security and Trust. — Censys-based census of internet-exposed ICS devices. Provides context for what scanning tools find.

- **Samtani, S., et al.** (2018). *Identifying SCADA Vulnerabilities Using Passive and Active Vulnerability Assessment Techniques.* IEEE Conference on Intelligence and Security Informatics. — Combines dark web intelligence with honeypot data.

## Deployment Methodologies

- **Vasilomanolakis, E., et al.** (2016). *Multi-Stage Attack Detection and Signature Generation with ICS Honeypots.* IEEE/IFIP Network Operations and Management Symposium. — Proposes multi-stage attack detection using correlated honeypot events.

- **Hink, R. C. B., et al.** (2015). *Assessing and Reducing the Vulnerability of SCADA Systems.* In *Securing Critical Infrastructures and Critical Control Systems: Approaches for Threat Protection.* — Broader context for honeypot deployment within ICS security programs.

## Related Projects

- [Conpot](https://github.com/mushorg/conpot) — ICS/SCADA honeypot (Modbus, S7comm, BACnet, SNMP, HTTP)
- [GRFICSv2](https://github.com/Fortiphyd/GRFICSv2) — Virtual ICS environment for security research
- [GRFICS](https://github.com/djformby/GRFICS) — Original graphical realism framework for ICS
- [HoneyPLC](https://github.com/sefcom/honeyplc) — High-interaction PLC honeypot
- [Cowrie](https://github.com/cowrie/cowrie) — SSH/Telnet honeypot, often deployed alongside Conpot
- [T-Pot](https://github.com/telekom-security/tpotce) — Multi-honeypot platform that includes Conpot
- [OpenPLC](https://github.com/thiagoralves/OpenPLC_v3) — Open-source PLC runtime (can be used for high-interaction honeypots)

## Datasets

- [ICS-PCAP](https://github.com/automayt/ICS-pcap) — Collection of ICS protocol packet captures
- [Conpot log samples](https://github.com/mushorg/conpot/tree/main/docs) — Example output from Conpot protocol handlers

## Contributing

Know of a paper or project that should be listed here? Open an issue or submit a PR referencing this wiki page.
