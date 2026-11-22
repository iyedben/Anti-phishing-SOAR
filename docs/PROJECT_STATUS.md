# Project Status — Anti-Phishing SOAR Platform

## 1. Project Tracking Overview

| Phase | Description | Status | Evidence / Artifacts |
| :--- | :--- | :--- | :--- |
| **Phase 1** | Workspace & Environment Initialization | **Completed** | Directory structure, git repository initialized, `AGENTS.md` |
| **Phase 1.5** | Initial Architecture & Feasibility Study | **Completed** | Initial specifications (superseded by Phase 1.6) |
| **Phase 1.6** | Comprehensive Architecture Reassessment | **Completed** | Upstream archival, lifecycle, and baseline feasibility analysis |
| **Phase 1.7** | Final Architecture Validation & Resource Reconciliation | **Completed** | Reconciled memory budget, lifecycle validation, Cortex analysis, socket proxy hardening in `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT.md`, `README.md` |
| **Phase 2** | Staged Infrastructure Deployment (TheHive & Cortex) | **Completed (Stage 1A & 1B Validated)** | Stage 1A deployed (TheHive 4.1.24 + Cassandra 4.0 + ES 7.17.9, 7/7 tests passed); Stage 1B deployed (Cortex 3.1.8 + ES 7.17.9, 8/8 tests passed, Process analyzer verified); persistent volumes intact |
| **Phase 3** | Observable Enrichment & Cortex Analyzers | *Pending* | Process-based analyzer configs, threat intel test jobs, taxonomies |
| **Phase 4** | Shuffle SOAR Deployment & Workflow Design | *Pending* | Playbook JSON exports, socket proxy, webhook receiver, risk scorer |
| **Phase 5** | Simulated Containment & Human-in-the-Loop | *Pending* | Mock containment microservice, approval node, audit logs |
| **Phase 6** | End-to-End Testing & Incident Reporting | *Pending* | Automated E2E test suite (`scripts/test_pipeline.py`), incident reports |

---

## 2. Phase 1.7 Validation Findings Summary

### 2.1 Reconciled Resource Budget & Deficit Analysis
- **Guest Physical Memory (`MemTotal`):** 4,009,584 kB (**3,915.6 MiB / ~3.82 GiB**).
- **Host Desktop Memory Baseline:** **~1,018 MiB** used by GNOME/Xorg/systemd.
- **Available Headroom for Docker:** **~2,638 MiB**.
- **Stage 1 Previous Estimate:** 3,450 MB containers + 1,018 MB Host OS = **4,468 MB**.
- **Reconciliation Finding:** Claiming Stage 1 fits in physical RAM was mathematically invalid (-553 MB deficit vs `MemTotal`; -812 MB vs available RAM).
- **Defensible Strategies on Current VM:**
  - *Strategy A (Sub-Staged Execution):* Stage 1A (TheHive + ES + Cassandra = 2,050 MB container RSS) leaves ~847 MiB physical RAM headroom; Stage 1B (Cortex + ES = 1,400 MB container RSS) leaves ~1,497 MiB headroom. Zero swap required.
  - *Strategy B (Concurrently with Swap):* Down-tuned aggregate container RSS (~2,650 MB) + Host OS (~1,018 MB) touches 150–400 MB swap during startup spikes.

### 2.2 Integration Lifecycle & Test Categorization
- Stopping TheHive/Cortex before running Shuffle makes **live runtime REST calls between Shuffle and TheHive/Cortex impossible**.
- Test methodologies are formally categorized into:
  - **Category 1 (Component & Staged API Integration Tests):** Real components tested against real REST APIs in isolated stages; cross-platform validation via staged data verification.
  - **Category 2 (Full Simultaneous Live End-to-End Pipeline):** Real-time automated workflow (`Webhook -> Shuffle -> live Cortex -> risk scoring/approval -> mock containment -> live TheHive`). Requires 8 GiB VM RAM allocation.

### 2.3 TheHive 4.1.24 Status & Specification Compliance
- Upstream repository (`TheHive-Project/TheHive`) archived Dec 5, 2025; TheHive 4.1.24 reached EOL Dec 31, 2022. It is unmaintained legacy software.
- The project specification (`AGENTS.md`) requires "TheHive for incident and case management", but does not prescribe a specific version.
- Academic selection justification: 100% open-source AGPLv3 licensing; zero portal challenge-response keys or SaaS registration locks; deterministic offline reproducibility.

### 2.4 Cortex Analyzer Execution Verification
- Analyzers can run in **Docker Mode** (StrangeBee default for Cortex 3+) or **Process Mode** (legacy/subprocess).
- Target analyzers for phishing pipeline (VirusTotal, AbuseIPDB/URLhaus) are lightweight HTTP REST API clients and **can run via Process Mode** without Docker, provided Python 3, `cortexutils`, and `requests` are provisioned in a virtualenv.
- File-centric or sandboxing analyzers (YARA, Cuckoo, ssdeep) would require Docker execution.

### 2.5 Docker Socket Proxy Hardening
- Shuffle Orborus requires: `CONTAINERS=1`, `IMAGES=1`, `NETWORKS=1`, and `POST=1` to orchestrate ephemeral worker containers.
- `POST=1` is strictly required because container creation/start and image pulls are HTTP POST requests.
- All other API endpoints (`VOLUMES=0`, `EXEC=0`, `INFO=0`, `SYSTEM=0`, `SWARM=0`, `NODES=0`, `SECRETS=0`) are explicitly disabled to prevent host compromise.
- Socket proxy port 2375 is never published to the host network.

### 2.6 Feasibility of 8 GiB VM Memory Upgrade
- Host has 16 GB physical RAM and 8C/16T Ryzen 7 4800H processor.
- Allocating 8 GB RAM and 4 vCPUs leaves ~7.5 GB for Windows 10/11 host, which is safe and viable.
- This expands guest available RAM to ~6.8 GB, allowing all components (~5.15 GiB combined RSS) to run simultaneously in physical RAM with ~2.5 GB headroom, unlocking **Category 2 Live Simultaneous E2E Testing**.

### 2.7 Phase 2 / Stage 1A Empirical Deployment & Validation
- **Deployment Artifact:** `infrastructure/docker/docker-compose.stage1a.yml` deploying Cassandra 4.0, Elasticsearch 7.17.9, and TheHive 4.1.24-1.
- **Security & Secret Isolation:** Credentials isolated in `infrastructure/docker/.env` (excluded via `.gitignore`), with template in `.env.example`.
- **Network & Host Isolation:** Internal databases (Cassandra 9042, Elasticsearch 9200) run strictly on internal Docker bridge network `soar_backend_net` with no host-published ports. TheHive web/API interface binds exclusively to `127.0.0.1:9000` (loopback only).
- **Measured Empirical Resource Usage (Steady State):**
  - Cassandra 4.0: **~540 MiB RSS** (70.4% of 768 MiB limit, ~8.6% CPU).
  - Elasticsearch 7.17.9: **~663 MiB RSS** (64.8% of 1,024 MiB limit, ~1.2% CPU).
  - TheHive 4.1.24-1: **~540 MiB RSS** (67.6% of 800 MiB limit, ~3.6% CPU).
  - Total Stage 1A Container RSS: **~1,743 MiB (~1.70 GiB)**.
  - Host RAM Headroom: **~1.2 GiB available memory** on 3.82 GiB VM.
  - Swap Impact: Initial schema generation burst touched 546 MiB swap; zero swap growth or thrashing during steady-state operations.
- **Automated Validation Results (`scripts/validate_stage1a.py` / `tests/test_stage1a_thehive.py`):**
  - `test_01_health_and_status`: HTTP 200 OK, TheHive 4.1.24-1, JanusGraph schema version 99 (expected 99, error null).
  - `test_02_admin_authentication`: Default admin (`admin@thehive.local`) authenticated successfully.
  - `test_03_ensure_soc_organisation`: Tenant organisation `SOC` verified and provisioned.
  - `test_04_ensure_analyst_user_and_api_key`: SOAR service user created with `org-admin` profile and Bearer API key generated.
  - `test_05_create_phishing_case_with_api_key`: Synthetic phishing case created via Bearer token (`caseId: 1`, HTTP 201 Created).
  - `test_06_attach_observables_to_case`: Attached phishing URL and SMTP relay IP observables to case.
  - `test_07_retrieve_and_verify_persistence`: Verified persistent storage and Elasticsearch indexing of case and observables.
  - Result: **7/7 tests passed cleanly.**

### 2.8 Phase 2 / Stage 1B Empirical Deployment & Validation
- **Deployment Artifact:** `infrastructure/docker/docker-compose.stage1b.yml` deploying dedicated Elasticsearch 7.17.9 and Cortex 3.1.8-1.
- **Dedicated Elasticsearch Instance:** Adhered strictly to vendor recommendation against index sharing; deployed isolated `cortex_elasticsearch` with independent index volume `soar_cortex_elasticsearch_data` on internal bridge `cortex_backend_net`.
- **Security & Port Isolation:**
  - `cortex_elasticsearch` (9200) internal only with no host bindings.
  - Cortex web/API interface binds exclusively to `127.0.0.1:9001` (host loopback only).
  - CSRF protection verified: session-based authentication requires `X-CORTEX-XSRF-TOKEN` matching session cookie; API Bearer token authentication operates seamlessly for automation.
- **Measured Empirical Resource Usage (Steady State):**
  - Cortex 3.1.8: **~364.1 MiB RSS** (45.5% of 800 MiB limit, ~2.2% CPU).
  - Cortex Elasticsearch 7.17.9: **~676.7 MiB RSS** (66.1% of 1,024 MiB limit, ~1.0% CPU).
  - Total Stage 1B Container RSS: **~1,040.8 MiB (~1.02 GiB)**.
  - Host RAM Headroom: **~1.3 GiB available memory** on 3.82 GiB VM.
  - Swap Impact: **470 MiB used** (decreased from 546 MiB, zero swap thrashing).
- **Automated Validation Results (`scripts/validate_stage1b.py` / `tests/test_stage1b_cortex.py`):**
  - `test_01_health_and_status`: HTTP 200 OK, Cortex 3.1.8-1, ElasticSearch client 7.17.1, Play 2.8.19.
  - `test_02_superadmin_auth_and_api_key`: SuperAdmin user `admin` authenticated via CSRF-protected session, Bearer API key renewed.
  - `test_03_organization_management`: Verified default `cortex` org; provisioned `SOC` tenant organization.
  - `test_04_user_provisioning_and_rbac`: Created `soar-analyst` user in `SOC` org with `read`, `analyze`, `orgadmin` roles; renewed analyst Bearer API key; verified RBAC isolation (analyst cannot access global `/api/organization`).
  - `test_05_analyzer_definition_discovery`: Triggered `POST /api/analyzerdefinition/scan` and verified `MockPhishing_1_0` definition discovery from `/opt/cortex/analyzers`.
  - `test_06_enable_analyzer_for_organization`: Activated `MockPhishing` analyzer worker in `SOC` tenant organization.
  - `test_07_execute_phishing_url_analysis`: Submitted phishing URL observable (`http://evil-phishing-login.example.com/verify`) to analyzer; job polled through `Waiting` -> `InProgress` -> `Success` in 2 seconds.
  - `test_08_verify_analysis_report_and_verdict`: Extracted full JSON report; verified `verdict: malicious`, `score: 90`, and taxonomy `MockTI:Malicious`.
  - Result: **8/8 tests passed cleanly.**
- **TheHive-to-Cortex Simultaneous Integration Status:**
  - Live simultaneous execution remains **unverified** due to 4.44 GiB combined demand exceeding the 3.82 GiB physical RAM allocation.
  - The connector configuration syntax has been inspected and extracted directly from TheHive 4 libraries (`connectors.cortex.CortexConnector`) and prepared for Phase 3.
  - Stage 1A persistent data volumes (`soar_thehive_data`, `soar_cassandra_data`, `soar_elasticsearch_data`) verified completely intact.

---

## 3. Decision Matrix & Recommendations

| Architecture Option | RAM Feasibility | Integration Mode | Academic Fidelity | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **Option A: Monolith on 3.82 GiB VM** | Fails (OOM crash) | Broken | Zero | **REJECTED** |
| **Option B: 8 GiB VM Allocation** | Fully feasible (~2.5 GB headroom) | **Category 2 Live Simultaneous E2E** | **Maximum (Authentic Live Pipeline)** | **PRIMARY RECOMMENDATION** |
| **Option C: Sub-Staged on 3.82 GiB VM** | Feasible (Within RAM limits) | Category 1 Staged API Tests | High (Components); Limited (Live E2E) | **OFFICIAL FALLBACK (Stage 1A Verified)** |
| **Option D: Custom Mock Stack** | Feasible (< 1.5 GB RAM) | Simulated / Mocked | Low (No real SOAR/Case engine) | **REJECTED** |

---

## 4. Safety & Operational Constraints Verified
- **Preserved Existing Data:** Existing unrelated containers (`minikube`, `angry_edison`) left untouched and unmodified.
- **Controlled Image Pull:** Only Stage 1A images (`cassandra:4.0`, `elasticsearch:7.17.9`, `thehiveproject/thehive4:4.1.24-1`) downloaded.
- **Zero Raw Socket Access:** No Docker socket mounted into TheHive or database containers.
- **Zero Destructive Actions:** All tests run with synthetic observables in an isolated Docker environment.
- **Secrets Excluded:** `.gitignore` active and verified; no credentials committed.
