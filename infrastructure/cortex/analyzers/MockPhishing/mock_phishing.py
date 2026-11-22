#!/usr/bin/env python3
"""
Academic Mock Threat Intelligence Analyzer for Phishing Observables
Complies with Cortex Process Analyzer Protocol.
"""
import sys
import os
import json

def main():
    if len(sys.argv) < 2:
        print("Missing job directory argument", file=sys.stderr)
        sys.exit(1)

    job_dir = sys.argv[1]
    input_path = os.path.join(job_dir, "input", "input.json")

    if not os.path.exists(input_path):
        print(f"Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    data_type = data.get("dataType", "unknown")
    observable = data.get("data", "")

    # Phishing detection heuristic
    malicious_indicators = ["phish", "evil", "malicious", "attack", "login-fake", "credential", "198.51.100."]
    is_malicious = any(indicator in str(observable).lower() for indicator in malicious_indicators)

    verdict = "malicious" if is_malicious else "safe"
    risk_score = 90 if is_malicious else 10

    report = {
        "success": True,
        "summary": {
            "verdict": verdict,
            "score": risk_score,
            "taxonomy": f"MockTI:{verdict.title()}"
        },
        "full": {
            "observable": observable,
            "dataType": data_type,
            "verdict": verdict,
            "risk_score": risk_score,
            "threat_intel_source": "Academic Mock TI Analyzer",
            "categories": ["credential-phishing", "impersonation"] if is_malicious else ["benign"],
            "simulation": True
        }
    }

    output_dir = os.path.join(job_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "output.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(0)

if __name__ == "__main__":
    main()
