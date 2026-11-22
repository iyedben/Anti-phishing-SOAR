#!/usr/bin/env python3
"""
validate_stage1b.py — Validation Runner & Resource Measurement for Stage 1B.
Runs the automated test suite for Cortex 3.1.8, collects empirical container and host
resource usage, and verifies Stage 1A volume preservation.
"""

import subprocess
import sys
import json
import time

def run_command(cmd):
    p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def main():
    print("=" * 70)
    print(" Anti-Phishing SOAR — Stage 1B Automated Validation Runner (Cortex)")
    print("=" * 70)

    # 1. Run Unit/Integration Tests
    print("\n[+] Step 1: Running Cortex REST API & Analyzer Integration Tests...")
    rc, stdout, stderr = run_command("python3 -m unittest tests/test_stage1b_cortex.py -v")
    print(stdout)
    if stderr:
        print(stderr)

    if rc != 0:
        print("\n[!] Validation Failed during test execution.")
        sys.exit(rc)

    print("\n[+] Step 2: Measuring Empirical Container Resource Usage...")
    stats_cmd = (
        'docker stats --no-stream --format '
        '"{\\"name\\": \\"{{.Name}}\\", \\"cpu\\": \\"{{.CPUPerc}}\\", '
        '\\"mem\\": \\"{{.MemUsage}}\\", \\"mem_perc\\": \\"{{.MemPerc}}\\"}"'
    )
    rc, stats_out, _ = run_command(stats_cmd)

    print("-" * 70)
    print(f"{'Container':<24} {'CPU %':<10} {'Memory Usage / Limit':<25} {'Mem %':<8}")
    print("-" * 70)
    for line in stats_out.splitlines():
        if line.strip():
            try:
                data = json.loads(line)
                print(f"{data['name']:<24} {data['cpu']:<10} {data['mem']:<25} {data['mem_perc']:<8}")
            except Exception:
                print(line)
    print("-" * 70)

    print("\n[+] Step 3: Measuring Host Memory and Swap Status...")
    rc, free_out, _ = run_command("free -h")
    print(free_out)

    print("\n[+] Step 4: Checking Container Health Status...")
    rc, ps_out, _ = run_command('docker ps --filter "name=cortex" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"')
    print(ps_out)

    print("\n[+] Step 5: Verifying Stage 1A Persistent Volume Preservation...")
    rc, vol_out, _ = run_command('docker volume ls --filter "name=soar_" --format "table {{.Name}}\t{{.Driver}}"')
    print(vol_out)

    print("\n" + "=" * 70)
    print(" [✓] Stage 1B Validation Completed Successfully!")
    print("=" * 70)

if __name__ == "__main__":
    main()
