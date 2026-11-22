# Anti-Phishing SOAR — Project Instructions

## Project objective
Build an academic Anti-Phishing SOAR platform integrating:
- Shuffle for SOAR orchestration
- TheHive for incident and case management
- Cortex for observable analysis and enrichment

## Environment
- Ubuntu Desktop 24.04 LTS
- VirtualBox VM
- Docker Engine and Docker Compose
- 3 vCPUs
- Approximately 3.82 GiB Docker-accessible RAM
- 50 GB virtual disk
- Project directory: ~/projects/anti-phishing-soar

## Functional requirements
1. Receive phishing alerts through a JSON webhook.
2. Extract URLs, domains, IP addresses, file hashes, and sender addresses.
3. Enrich observables using at least two threat-intelligence sources.
4. Calculate an explainable risk score from 0 to 100.
5. Require analyst approval before containment when the score is >= 70.
6. Perform simulated containment only.
7. Create and update TheHive cases with evidence and a timeline.
8. Notify analysts and generate closure reports.

## Risk thresholds
- 0–39: Low — automatic closure when justified.
- 40–69: Medium — analyst review.
- 70–100: Critical — analyst approval before simulated containment.

## Mandatory safety constraints
- Never block real URLs or IP addresses.
- Never isolate real hosts.
- Never disable real user accounts.
- Never execute destructive actions against external systems.
- Use mock APIs or local simulations for containment.
- Keep credentials out of source code and Git.
- Make workflows idempotent and auditable.
- Include retry and escalation behavior for unavailable services.
- Provide a dry-run mode.

## Implementation constraints
- Prefer free and open-source components.
- Use Docker Compose for deployment.
- Deploy and validate components incrementally.
- Avoid unnecessary services and resource-heavy configurations.
- Do not deploy all services simultaneously without checking resource requirements.
- Do not introduce a SIEM or build a phishing detection engine.
- Keep documentation and tests synchronized with implementation.

## Working method
- Inspect existing files before modifying them.
- Make small, verifiable changes.
- Explain commands before asking the user to execute them.
- Never claim a feature works without test evidence.
- Update README.md and docs/PROJECT_STATUS.md as work progresses.
