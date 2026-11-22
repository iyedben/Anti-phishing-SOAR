# Deployment & Feasibility Specification — Anti-Phishing SOAR Platform

## 1. Environmental Baseline & Host Specifications

The host environment has been inspected directly on the virtualized machine:

| Metric | Specification / Measured Value | Verification Source | System Boundary / Constraint |
| :--- | :--- | :--- | :--- |
| **Operating System** | Ubuntu Desktop 24.04.5 LTS (Noble Numbat) | `/etc/os-release` | Linux 6.8 kernel, cgroups v2 enabled |
| **vCPUs** | 3 vCPUs | `lscpu` (`NUMA node0 CPU(s): 0-2`) | AMD Ryzen 7 4800H host (VirtualBox allocation) |
| **Hypervisor RAM Allocation** | ~4,096 MB | VirtualBox VM settings | Memory allocated by hypervisor to the guest machine |
| **Guest Physical Memory (`MemTotal`)** | 4,009,584 kB (**3,915.6 MiB / ~3.82 GiB**) | `cat /proc/meminfo` | Total physical RAM visible to guest Linux kernel |
| **Host Desktop Memory Baseline** | ~1,018 MiB used | `free -m` (`Mem: 1018 used`) | GNOME Desktop, Xorg, mutter, systemd services |
| **Unallocated Memory for Workloads** | **~2,638 MiB (~2.57 GiB)** | `free -m` (`Mem: 2638 available`) | True unallocated headroom before memory pressure |
| **Swap Partition** | 3,219 MiB (**~3.1 GiB**) | `free -m` (`Swap: 3219 total`) | Located on `/dev/sda3` |
| **Disk Capacity & Storage** | 49 GB total / 20 GB used / **28 GB free** | `df -h /` | Local virtual disk image |
| **Docker Engine & CLI** | Docker Engine 29.10.0, Compose v5.8.0 | `docker --version`, `docker compose version` | Daemon active, rootless group access enabled |

---

## 2. Rigorous Memory Terminology & Distinctions

To prevent ambiguity and invalid feasibility claims, resource discussions strictly adhere to the following definitions:

1. **Guest Physical Memory (`MemTotal`):** Total RAM assigned by the hypervisor and recognized by the guest Linux kernel (`3,915.6 MiB`). This is the absolute hard ceiling of non-swapped memory.
2. **Host Desktop Memory:** RAM consumed by host kernel structures, page tables, and non-Docker user-space desktop daemons (GNOME Shell, Mutter, Xorg, systemd). Currently measured at **~1,018 MiB**.
3. **JVM Heap (`-Xms` / `-Xmx`):** Memory reserved inside the Java Virtual Machine for Java object instances and garbage collection. *This is only a subset of the process memory.*
4. **Container RSS (Resident Set Size):** The actual non-swapped physical memory occupied in host RAM by the container's processes. For a JVM container:
   $$\text{Container RSS} = \text{JVM Heap} + \text{Metaspace (128–256 MB)} + \text{Native Threads (100–200 MB)} + \text{GC/Native Buffers (100 MB)} + \text{Base OS (50 MB)}$$
   Typically, JVM Container RSS is **1.5× to 2.0× the `-Xmx` heap value**.
5. **Docker Memory Limit (`mem_limit` / cgroup `memory.max`):** Hard limit enforced by the Linux cgroup controller. If container RSS exceeds this limit, the Linux kernel OOM-killer immediately sends `SIGKILL` (exit code 137). The Docker limit must always be set above the expected JVM RSS.
6. **Swap Storage:** Disk-backed paging partition on `/dev/sda3` (**3,219 MiB**). Paging anonymous JVM heap pages to disk introduces 30–60 second latency spikes, causing GC pauses and network read timeouts.

---

## 3. Resource Consumption Categorization

Resource figures are strictly separated into three categories:

### 3.1 Category 1: Official Vendor Recommendations (Upstream Docs)

| Service | Vendor-Specified Minimum / Recommendation | Documentation Source | Significance |
| :--- | :--- | :--- | :--- |
| **Shuffle Stack** | **4 GB RAM** minimum for testing;<br>**8 GB RAM & 4 vCPUs** recommended | [Shuffle Onboarding Guide](https://shuffle.security/docs/onboarding) | Intended for basic multi-app execution |
| **Shuffle OpenSearch** | **3,072 MB JVM Heap** (`-Xms3g -Xmx3g`) | [Shuffle Default docker-compose.yml](https://github.com/Shuffle/Shuffle/blob/main/docker-compose.yml) | Default DB heap alone consumes ~80% of our total RAM |
| **TheHive & Cortex** | **8 GB RAM & 4 vCPUs** (Testing profile);<br>**16 GB RAM & 8 vCPUs** (Production) | [StrangeBee System Requirements](https://docs.strangebee.com/thehive/installation/system-requirements/) | Baseline testing profile for TheHive + Cortex |
| **Elasticsearch** | **50% of system RAM** up to 30 GB heap;<br>Minimum 2 GB to 4 GB heap | [Elasticsearch Sizing Documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/advanced-configuration.html) | Search engine heap for index caching |
| **Apache Cassandra** | **2 GB to 4 GB JVM Heap** for testing;<br>8 GB+ heap for production | [Apache Cassandra Hardware Requirements](https://cassandra.apache.org/_/quickstart.html) | Distributed database memory for memtables |
| **TOTAL VENDOR DEMAND** | **12 GB to 16+ GB RAM / 8 vCPUs** | Upstream Documentation Aggregation | **Over 300% to 400% of our VM's physical RAM** |

### 3.2 Category 2: Estimated Minimum Lab Configurations (Theoretical Down-Tuned Lower Bounds)

These figures represent theoretical lower bounds where JVM heaps and container memory limits are aggressively capped to the lowest possible threshold required for Java processes to boot without immediate runtime crashes:

| Service / Layer | Image / Process | Theoretical Minimal Heap | Estimated Minimum RSS Memory | Sizing Justification |
| :--- | :--- | :--- | :--- | :--- |
| **Host Operating System** | Host processes (GNOME/Kernel) | N/A | **~1,018 MB** (Measured) | Desktop environment baseline |
| **Elasticsearch 7.17** | `docker.elastic.co/elasticsearch` | `-Xms384m -Xmx512m` | **~800 MB** (Estimate) | Minimum heap for Lucene index mappings + off-heap |
| **Apache Cassandra 4.0** | `cassandra:4.0` | `MAX_HEAP_SIZE=384M` | **~650 MB** (Estimate) | JanusGraph case storage + JVM off-heap |
| **TheHive 4.1.24** | `thehiveproject/thehive4` | `-Xms384m -Xmx384m` | **~600 MB** (Estimate) | Play framework, Akka actors, JanusGraph client |
| **Cortex 3.1.8** | `thehiveproject/cortex` | `-Xms384m -Xmx384m` | **~600 MB** (Estimate) | Analyzer execution queue, job manager |
| **Shuffle Backend & Web**| `shuffle-backend` / `frontend` | Python/Go runtime | **~350 MB** (Estimate) | Workflow runner and UI web server |
| **Docker Socket Proxy** | `tecnativa/docker-socket-proxy` | HAProxy C binary | **~30 MB** (Estimate) | Low-footprint filtered socket gateway |
| **Shuffle DB (OpenSearch)**| Down-tuned OpenSearch | `-Xms384m -Xmx512m` | **~800 MB** (Estimate) | Down-tuned workflow execution history |
| **Mock Containment** | Python 3.12 / FastAPI | Python runtime | **~30 MB** (Estimate) | Lightweight simulation microservice |
| **TOTAL COMBINED STACK** | | | **~5,278 MB (~5.15 GiB)** | **Exceeds total physical RAM by > 1.3 GiB** |

### 3.3 Category 3: Actual Measured Resource Consumption

Empirical measurements gathered directly from the operating system:

| Target | Measured Memory (RAM) | Measured Disk Usage | Status / Notes |
| :--- | :--- | :--- | :--- |
| **Host System Baseline** | **1,018 MiB** used / **2,638 MiB** available | 20 GB used / 28 GB free | Clean desktop state, no user apps running |
| **Swap Usage** | **0 MiB** used (3,219 MiB total free) | N/A | No memory pressure on idle host |
| **Docker Daemon Overhead** | Negligible (< 50 MiB) | Part of host baseline | Daemon idle |
| **Running Service Containers**| **0 MiB (0 containers running)** | 0 GB volume data | **No containers have been pulled or started** |

> [!IMPORTANT]
> All application container memory figures in Section 3.2 are theoretical engineering estimates. Because no containers have been deployed yet (in strict accordance with Phase 1 safety constraints), **there are zero measured container runtime figures**.

---

## 4. Reconciliation of Stage 1 Resource Calculations

### 4.1 The Mathematical Deficit in Previous Calculations
In Phase 1.6, the Stage 1 container estimates were:
- Elasticsearch: ~1,100 MB RSS
- Cassandra: ~850 MB RSS
- TheHive: ~750 MB RSS
- Cortex: ~750 MB RSS
- **Total Stage 1 Container RSS:** **3,450 MB (~3.37 GiB)**

When combined with the host desktop memory baseline:
$$\text{Total System Demand} = 3,450 \text{ MB (Containers)} + 1,018 \text{ MB (Host OS)} = \mathbf{4,468 \text{ MB (~4.36 GiB)}}$$

Comparing this against the host physical limits:
- **Guest Physical Memory (`MemTotal`):** **3,915.6 MiB (~3.82 GiB)**
- **Physical RAM Deficit:** $4,468 \text{ MB} - 3,915 \text{ MB} = \mathbf{-553 \text{ MB}}$
- **Deficit against Available RAM (`MemAvailable` 2,638 MiB):** $3,450 \text{ MB} - 2,638 \text{ MB} = \mathbf{-812 \text{ MB}}$

### 4.2 Defensible Memory Budget & Staging Strategies

To run safely without uncontrolled OOM failures on the current 3.82 GiB VM, we must reconcile this deficit through one of two defensible strategies:

#### Strategy A: Sub-Staged Execution (True Zero-Swap Footprint)
Stage 1 is divided into two sequential sub-stages so that peak memory never exceeds physical capacity:
1. **Sub-Stage 1A (Database & Case Management):**
   - Host OS: ~1,018 MB
   - Cassandra 4.0 (`MAX_HEAP_SIZE=384M`): ~650 MB RSS
   - Elasticsearch 7.17 (`-Xmx512m`): ~800 MB RSS
   - TheHive 4.1.24 (`-Xmx384m`): ~600 MB RSS
   - **Total RSS in Sub-Stage 1A:** **~3,068 MB (~3.0 GiB)**
   - **Headroom:** **~847 MiB remaining within physical RAM.** (Zero swap usage).
   - *Verification:* Case management schema initialization, organization configuration, REST API case creation.
   - *Teardown:* Stop TheHive.
2. **Sub-Stage 1B (Observable Analysis & Threat Intel):**
   - Host OS: ~1,018 MB
   - Elasticsearch 7.17: ~800 MB RSS
   - Cortex 3.1.8 (`-Xmx384m`): ~600 MB RSS
   - **Total RSS in Sub-Stage 1B:** **~2,418 MB (~2.36 GiB)**
   - **Headroom:** **~1,497 MiB remaining within physical RAM.** (Zero swap usage).
   - *Verification:* Cortex organization setup, API key generation, observable analysis testing.

#### Strategy B: Concurrently Running Stage 1 with Documented Swap Utilization
If Cassandra, Elasticsearch, TheHive, and Cortex must run at the same time:
- The four containers are down-tuned to an aggregate of **~2,650 MB RSS**.
- Combined with Host OS (~1,018 MB), total demand is **~3,668 MB**.
- While this technically falls just under `MemTotal` (3,915 MiB), JVM allocation spikes during startup will push **150–400 MB into the 3,219 MiB swap partition**.
- *Operational Constraint:* JVM timeouts and Docker health checks must be extended to 120 seconds to tolerate swap-induced GC pauses.

---

## 5. Feasibility Assessment: 8 GiB VM Memory Upgrade

### 5.1 Host System Context
- **Physical Host:** Windows 10/11 Desktop, AMD Ryzen 7 4800H (8 physical cores / 16 threads), **16 GB physical RAM**.
- **Current VM Allocation:** 3 vCPUs, ~4,096 MB RAM (visible as 3,915 MiB in guest).

### 5.2 Technical Feasibility & Host Impact of Upgrading to 8 GiB / 4 vCPUs
1. **Impact on Windows Host:**
   - Windows 10/11 baseline consumption: ~4.0 to 5.0 GB RAM.
   - Allocating **8.0 GB RAM to the VM**:
     $$\text{Host RAM In-Use} \approx 5.0 \text{ GB (Windows)} + 8.0 \text{ GB (VM)} + 0.5 \text{ GB (Hypervisor Overhead)} = \mathbf{13.5 \text{ GB}}$$
   - **Remaining Host Headroom:** **~2.5 GB**.
   - *Verdict:* Safe and stable on a 16 GB host, provided memory-intensive host applications (video rendering, heavy local databases) are not active simultaneously.
2. **Impact on vCPU Allocation:**
   - Ryzen 7 4800H provides 8 physical cores and 16 logical threads.
   - Allocating **4 vCPUs** to VirtualBox leaves 12 logical threads for the Windows host, eliminating CPU starvation risks.
3. **Material Impact on SOAR Architecture:**
   - Expands guest visible RAM to **~8,000 MiB (~7.8 GiB)**.
   - Available unallocated RAM for Docker workloads expands from **2,638 MiB to ~6,800 MiB (~6.6 GiB)**.
   - **Simultaneous Full-Stack Demand:** Down-tuned full stack requires **~5,278 MB (~5.15 GiB)**.
   - **Result:** The entire platform (Shuffle, TheHive, Cortex, Elasticsearch, Cassandra, Socket Proxy, Mock Containment) can run **simultaneously in physical RAM with ~2.5 GiB of safety headroom**.
   - **Enables Category 2 Live Simultaneous End-to-End Pipeline:** Eliminates the need to stop services between stages; Shuffle can make live real-time HTTP calls directly to TheHive and Cortex.

> [!NOTE]
> Per project constraints, the agent will **not modify VirtualBox settings**. This upgrade is presented as an architectural recommendation for user evaluation.

---

## 6. Docker Socket Proxy Security Configuration

### 6.1 Least-Privilege Permission Justification for Shuffle Orborus

```yaml
services:
  docker-socket-proxy:
    image: tecnativa/docker-socket-proxy:latest
    container_name: docker-socket-proxy
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      # MINIMUM REQUIRED PRIVILEGES FOR SHUFFLE ORBORUS:
      - CONTAINERS=1   # Required: create, start, inspect, stream logs, wait, and delete worker containers
      - IMAGES=1       # Required: inspect local worker images and pull missing app images from GHCR
      - NETWORKS=1     # Required: attach worker containers to internal shuffle_backend_net
      - POST=1         # Required: container create/start, image pull, and network connect are POST endpoints
      # EXPLICITLY DISABLED DANGEROUS PRIVILEGES (LEAST-PRIVILEGE POLICY):
      - VOLUMES=0      # Blocked: prevents mounting host filesystem or creating persistent volumes
      - EXEC=0         # Blocked: prevents injecting interactive commands into existing containers
      - INFO=0         # Blocked: prevents host architecture and Docker daemon telemetry leakage
      - SYSTEM=0       # Blocked: prevents host system state manipulation
      - SWARM=0        # Blocked: standalone Docker Engine; Swarm endpoints disabled
      - NODES=0        # Blocked: Swarm node management disabled
      - SECRETS=0      # Blocked: Swarm secret store disabled
      - CONFIGS=0      # Blocked: Swarm configs disabled
      - AUTH=0         # Blocked: Docker registry credential modification disabled
      - BUILD=0        # Blocked: Dockerfile building disabled
    networks:
      - shuffle_backend_net
    # CRITICAL: Do NOT expose or publish port 2375 to host network
```

### 6.2 Cortex Process-Based Execution
Cortex is configured to execute analyzers via **Process Mode** using local Python scripts, avoiding any access to `/var/run/docker.sock` or the proxy.

---

## 7. Host Kernel Tuning & Prerequisites

Before deploying containers in Phase 2, the following host settings must be applied:

```bash
# 1. Virtual memory map areas for Elasticsearch / OpenSearch (Mandatory)
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf

# 2. File descriptor limits
ulimit -n 65536
```

---

## 8. Safety, Rollback & Teardown Protocol

- **Volume Safety:** NEVER execute `docker volume prune` or `docker system prune -a`.
- **Graceful Stop (Memory Release without Data Loss):**
  ```bash
  docker compose -f infrastructure/docker/<target-stack>.yml stop
  ```
- **Clean Stack Teardown (Preserving Persistent Volumes):**
  ```bash
  docker compose -f infrastructure/docker/<target-stack>.yml down
  ```

---

## 9. Stage 1A Implementation & Operational Runbook

### 9.1 Deployed Architecture
Stage 1A implements the Database & Incident Management core of the platform:
- **Apache Cassandra 4.0:** JanusGraph distributed backend for graph case entities.
- **Elasticsearch 7.17.9:** Full-text indexing and searchable case/observable registry.
- **TheHive 4.1.24-1:** AGPLv3 incident management system with multi-tenancy and RBAC.

### 9.2 Configuration Structure & Security
All configuration files and persistent volumes are structured under `infrastructure/`:
```
infrastructure/
├── docker/
│   ├── .env.example               # Safe Git-tracked environment template
│   ├── .env                       # Local secrets (excluded from Git)
│   └── docker-compose.stage1a.yml # Stage 1A Compose stack definition
└── thehive/
    └── application.conf           # TheHive 4 JanusGraph & CQL configuration
```

**Security Protections:**
1. Credentials and Play Framework signing secret (`THEHIVE_PLAY_SECRET`) reside in `infrastructure/docker/.env` and are strictly ignored by Git.
2. Internal databases (Cassandra CQL `9042`, Elasticsearch `9200`) do not publish ports to the host; communication occurs strictly over `soar_backend_net`.
3. TheHive port 9000 is bound exclusively to host loopback (`127.0.0.1:9000:9000`), blocking unauthorized LAN or external access.

### 9.3 Operational Commands

#### 1. Startup
```bash
# Start Cassandra, Elasticsearch, and TheHive in detached mode
docker compose -f infrastructure/docker/docker-compose.stage1a.yml --env-file infrastructure/docker/.env up -d
```

#### 2. Health & Status Check
```bash
# Verify container health and port bindings
docker ps --filter "name=cassandra|elasticsearch|thehive" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Test TheHive API readiness
curl -s http://127.0.0.1:9000/api/status
```

#### 3. Automated Validation Suite
```bash
# Execute automated API integration tests and empirical resource reporting
python3 scripts/validate_stage1a.py
```

#### 4. Graceful Stop (Preserving Containers & In-Memory Buffers)
```bash
docker compose -f infrastructure/docker/docker-compose.stage1a.yml --env-file infrastructure/docker/.env stop
```

#### 5. Teardown (Removing Containers, Preserving Persistent Volumes)
```bash
docker compose -f infrastructure/docker/docker-compose.stage1a.yml --env-file infrastructure/docker/.env down
```

### 9.4 Measured Empirical Resource Footprint

Measurements taken during active API case creation and observable query validation on Ubuntu 24.04 LTS (3.82 GiB RAM VM):

| Container / Layer | CPU % | Memory RSS / Limit | Mem % | Ports | Storage Volume |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`thehive`** | ~3.6% | **540.6 MiB** / 800 MiB | 67.6% | `127.0.0.1:9000->9000/tcp` | `soar_thehive_data` |
| **`cassandra`** | ~8.6% | **540.8 MiB** / 768 MiB | 70.4% | Internal (`9042`, `7000`) | `soar_cassandra_data` |
| **`elasticsearch`** | ~1.2% | **663.1 MiB** / 1,024 MiB | 64.8% | Internal (`9200`, `9300`) | `soar_elasticsearch_data` |
| **Host System** | ~14% | **2.4 GiB used** / **1.2 GiB available** | — | — | Virtual disk (`/dev/sda3`) |
| **Swap Space** | — | **546 MiB used** / 3.1 GiB | 17.2% | — | Stable (no active paging) |

*Validation Result:* 100% of automated tests passed (7/7 tests). Services maintained zero downtime, zero OOM terminations, and steady-state memory utilization well within the VM capacity.

---

## 10. Stage 1B Implementation & Operational Runbook (Cortex)

### 10.1 Deployed Architecture
Stage 1B implements the Threat Intelligence & Observable Analysis core:
- **Dedicated Elasticsearch 7.17.9 (`cortex_elasticsearch`):** Isolated search engine instance dedicated to Cortex. Adheres to StrangeBee's vendor recommendation against sharing Elasticsearch with TheHive to prevent mapping collisions and resource contention.
- **Cortex 3.1.8-1:** AGPLv3 observable analysis engine configured for Process Mode execution.
- **Process Mode Analyzer (`MockPhishing`):** Lightweight Python analyzer running directly inside the container without Docker socket privileges, providing simulated threat-intelligence scoring for URLs, domains, and IP addresses.

### 10.2 Configuration Structure & Security
```
infrastructure/
├── cortex/
│   ├── application.conf           # Cortex Play framework & ES backend config
│   └── analyzers/
│       └── MockPhishing/
│           ├── MockPhishing.json  # Analyzer definition manifest
│           └── mock_phishing.py   # Standalone Process mode analyzer script
└── docker/
    ├── .env.example               # Git-tracked environment template
    ├── .env                       # Active credentials (git-ignored)
    └── docker-compose.stage1b.yml # Stage 1B Compose stack definition
```

**Security Protections:**
1. Dedicated internal bridge network `cortex_backend_net` isolates `cortex_elasticsearch` (port 9200 is not exposed to host).
2. Cortex web/API interface binds exclusively to host loopback (`127.0.0.1:9001:9001`).
3. Zero Docker socket exposure: Cortex operates in pure **Process Mode** without mounting `/var/run/docker.sock`.
4. Role-Based Access Control (RBAC): SuperAdmin credentials isolated in `.env`; SOAR service user operates under restricted `SOC` organization with `read` and `analyze` roles.

### 10.3 Operational Commands

#### 1. Startup (Stage 1B)
```bash
# Start Cortex Elasticsearch and Cortex
docker compose -f infrastructure/docker/docker-compose.stage1b.yml --env-file infrastructure/docker/.env up -d
```

#### 2. Health & Status Check
```bash
# Verify container health and port bindings
docker ps --filter "name=cortex" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Test Cortex API status
curl -s http://127.0.0.1:9001/api/status
```

#### 3. Automated Validation Suite
```bash
# Run automated Cortex REST API, RBAC, and analyzer execution test suite
python3 scripts/validate_stage1b.py
```

#### 4. Graceful Stop
```bash
# Stop Stage 1B containers (releases memory for next stage)
docker compose -f infrastructure/docker/docker-compose.stage1b.yml --env-file infrastructure/docker/.env stop
```

#### 5. Teardown (Preserving Persistent Volumes)
```bash
# Remove Stage 1B containers while preserving index and job volumes
docker compose -f infrastructure/docker/docker-compose.stage1b.yml --env-file infrastructure/docker/.env down
```

### 10.4 Measured Empirical Resource Footprint

Measurements taken during active analyzer job execution on Ubuntu 24.04 LTS (3.82 GiB RAM VM):

| Container / Layer | CPU % | Memory RSS / Limit | Mem % | Ports | Storage Volume |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`cortex`** | ~2.2% | **364.1 MiB** / 800 MiB | 45.5% | `127.0.0.1:9001->9001/tcp` | `soar_cortex_data` |
| **`cortex_elasticsearch`** | ~1.0% | **676.7 MiB** / 1,024 MiB | 66.1% | Internal (`9200`, `9300`) | `soar_cortex_elasticsearch_data` |
| **Host System** | ~12% | **2.3 GiB used** / **1.3 GiB available** | — | — | Virtual disk (`/dev/sda3`) |
| **Swap Space** | — | **470 MiB used** / 3.1 GiB | 14.8% | — | Stable (no active paging) |

*Validation Result:* 100% of automated tests passed (8/8 tests). Observable analysis completed in ~2 seconds with zero Docker daemon access.
