#!/usr/bin/env python3
"""
test_stage1b_cortex.py — Automated Component and API Integration Tests for Stage 1B.
Validates Cortex 3.1.8 health, Elasticsearch connectivity, administrator authentication,
CSRF handling, organization management, RBAC, API key generation, analyzer definition discovery,
worker activation, observable analysis execution, and report extraction.
"""

import unittest
import requests
import time
import os

BASE_URL = os.environ.get("CORTEX_URL", "http://127.0.0.1:9001")
ADMIN_USER = os.environ.get("CORTEX_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("CORTEX_ADMIN_PASSWORD", "SuperSecretLabPassword123!")
ANALYST_USER = "soar-analyst"


class TestStage1BCortex(unittest.TestCase):
    admin_key = None
    analyst_key = None
    analyzer_id = None
    job_id = None

    @classmethod
    def setUpClass(cls):
        cls.session = requests.Session()

    def test_01_health_and_status(self):
        """Verify Cortex service status, Play engine, and Elasticsearch client version."""
        url = f"{BASE_URL}/api/status"
        resp = self.session.get(url, timeout=10)
        self.assertEqual(resp.status_code, 200, f"Expected 200 OK from /api/status, got {resp.status_code}")
        data = resp.json()

        versions = data.get("versions", {})
        self.assertEqual(versions.get("Cortex"), "3.1.8-1", f"Unexpected Cortex version: {versions.get('Cortex')}")
        self.assertEqual(versions.get("ElasticSearch client"), "7.17.1")
        self.assertEqual(versions.get("Play"), "2.8.19")

    def test_02_superadmin_auth_and_api_key(self):
        """Authenticate as superAdmin using CSRF protection and generate/renew admin API key."""
        # 1. Fetch CSRF token
        status_resp = self.session.get(f"{BASE_URL}/api/status", timeout=10)
        csrf_token = self.session.cookies.get("CORTEX-XSRF-TOKEN")
        self.assertIsNotNone(csrf_token, "CORTEX-XSRF-TOKEN cookie not received")

        headers = {
            "X-CORTEX-XSRF-TOKEN": csrf_token,
            "Content-Type": "application/json"
        }

        # 2. Login to obtain session cookie
        login_resp = self.session.post(
            f"{BASE_URL}/api/login",
            json={"user": ADMIN_USER, "password": ADMIN_PASSWORD},
            headers=headers,
            timeout=10
        )
        self.assertEqual(login_resp.status_code, 200, f"Admin login failed: {login_resp.text}")
        login_data = login_resp.json()
        self.assertEqual(login_data.get("id"), ADMIN_USER)
        self.assertIn("superadmin", login_data.get("roles", []))

        # 3. Renew / obtain API key using authenticated session
        csrf_token = self.session.cookies.get("CORTEX-XSRF-TOKEN", csrf_token)
        headers["X-CORTEX-XSRF-TOKEN"] = csrf_token

        renew_resp = self.session.post(
            f"{BASE_URL}/api/user/{ADMIN_USER}/key/renew",
            headers=headers,
            timeout=10
        )
        self.assertEqual(renew_resp.status_code, 200, f"Failed to renew admin key: {renew_resp.text}")
        key = renew_resp.text.strip().replace('"', '')
        self.assertTrue(len(key) >= 20, "Admin API key is unexpectedly short")
        TestStage1BCortex.admin_key = key

    def test_03_organization_management(self):
        """Verify default organization and ensure tenant organization 'SOC' exists using Bearer auth."""
        self.assertIsNotNone(TestStage1BCortex.admin_key, "Admin API key required")
        headers = {
            "Authorization": f"Bearer {TestStage1BCortex.admin_key}",
            "Content-Type": "application/json"
        }

        # Query all organizations (superadmin privilege)
        orgs_resp = requests.get(f"{BASE_URL}/api/organization", headers={"Authorization": f"Bearer {TestStage1BCortex.admin_key}"}, timeout=10)
        self.assertEqual(orgs_resp.status_code, 200, f"Failed to list organizations: {orgs_resp.text}")
        orgs = orgs_resp.json()
        org_names = [o.get("name") for o in orgs]
        self.assertIn("cortex", org_names, "Default 'cortex' organization missing")

        # Create 'SOC' organization if not present
        if "SOC" not in org_names:
            create_resp = requests.post(
                f"{BASE_URL}/api/organization",
                headers=headers,
                json={"name": "SOC", "description": "Security Operations Center"},
                timeout=10
            )
            self.assertEqual(create_resp.status_code, 201, f"Failed to create SOC organization: {create_resp.text}")

        # Verify SOC organization details
        soc_resp = requests.get(f"{BASE_URL}/api/organization/SOC", headers={"Authorization": f"Bearer {TestStage1BCortex.admin_key}"}, timeout=10)
        self.assertEqual(soc_resp.status_code, 200)
        self.assertEqual(soc_resp.json().get("name"), "SOC")

    def test_04_user_provisioning_and_rbac(self):
        """Provision analyst user in SOC org, renew analyst API key, and verify RBAC isolation."""
        self.assertIsNotNone(TestStage1BCortex.admin_key)
        admin_headers = {
            "Authorization": f"Bearer {TestStage1BCortex.admin_key}",
            "Content-Type": "application/json"
        }

        # Check or create analyst user
        search_resp = requests.post(
            f"{BASE_URL}/api/user/_search",
            headers=admin_headers,
            json={"query": {"_id": ANALYST_USER}},
            timeout=10
        )
        users = search_resp.json() if search_resp.status_code == 200 else []
        analyst_found = any(u.get("id") == ANALYST_USER for u in users)

        if not analyst_found:
            create_resp = requests.post(
                f"{BASE_URL}/api/user",
                headers=admin_headers,
                json={
                    "login": ANALYST_USER,
                    "name": "SOAR Analyst",
                    "roles": ["read", "analyze", "orgadmin"],
                    "organization": "SOC"
                },
                timeout=10
            )
            self.assertEqual(create_resp.status_code, 201, f"Failed to create analyst user: {create_resp.text}")

        # Renew/generate analyst API key
        key_resp = requests.post(
            f"{BASE_URL}/api/user/{ANALYST_USER}/key/renew",
            headers={"Authorization": f"Bearer {TestStage1BCortex.admin_key}"},
            timeout=10
        )
        self.assertEqual(key_resp.status_code, 200, f"Failed to renew analyst key: {key_resp.text}")
        analyst_key = key_resp.text.strip().replace('"', '')
        self.assertTrue(len(analyst_key) >= 20)
        TestStage1BCortex.analyst_key = analyst_key

        # Validate RBAC: Analyst can access own profile and own org
        analyst_headers = {"Authorization": f"Bearer {analyst_key}"}
        me_resp = requests.get(f"{BASE_URL}/api/user/current", headers=analyst_headers, timeout=10)
        self.assertEqual(me_resp.status_code, 200)
        me_data = me_resp.json()
        self.assertEqual(me_data.get("organization"), "SOC")
        self.assertIn("analyze", me_data.get("roles", []))

        # Validate RBAC: Analyst cannot access global /api/organization (superadmin only)
        forbidden_resp = requests.get(f"{BASE_URL}/api/organization", headers=analyst_headers, timeout=10)
        self.assertEqual(forbidden_resp.status_code, 403, "Analyst should not have global organization access")

    def test_05_analyzer_definition_discovery(self):
        """Trigger analyzer definition scanning and verify MockPhishing definition is registered."""
        self.assertIsNotNone(TestStage1BCortex.analyst_key)
        analyst_headers = {"Authorization": f"Bearer {TestStage1BCortex.analyst_key}"}

        # Trigger definition scan
        scan_resp = requests.post(f"{BASE_URL}/api/analyzerdefinition/scan", headers=analyst_headers, timeout=10)
        self.assertIn(scan_resp.status_code, [200, 204], f"Definition scan failed: {scan_resp.text}")

        # Query registered definitions
        defs_resp = requests.get(f"{BASE_URL}/api/analyzerdefinition", headers=analyst_headers, timeout=10)
        self.assertEqual(defs_resp.status_code, 200)
        definitions = defs_resp.json()
        self.assertTrue(len(definitions) > 0, "No analyzer definitions found")

        mock_def = next((d for d in definitions if d.get("name") == "MockPhishing"), None)
        self.assertIsNotNone(mock_def, "MockPhishing analyzer definition not found")
        self.assertEqual(mock_def.get("version"), "1.0")
        self.assertIn("url", mock_def.get("dataTypeList", []))
        self.assertIn("ip", mock_def.get("dataTypeList", []))
        self.assertIn("domain", mock_def.get("dataTypeList", []))

    def test_06_enable_analyzer_for_organization(self):
        """Enable the MockPhishing analyzer worker in the SOC organization."""
        self.assertIsNotNone(TestStage1BCortex.analyst_key)
        headers = {
            "Authorization": f"Bearer {TestStage1BCortex.analyst_key}",
            "Content-Type": "application/json"
        }

        # Check existing active analyzers
        list_resp = requests.get(f"{BASE_URL}/api/analyzer", headers={"Authorization": f"Bearer {TestStage1BCortex.analyst_key}"}, timeout=10)
        self.assertEqual(list_resp.status_code, 200)
        active_analyzers = list_resp.json()
        active_mock = next((a for a in active_analyzers if a.get("name") == "MockPhishing"), None)

        if not active_mock:
            enable_resp = requests.post(
                f"{BASE_URL}/api/organization/analyzer/MockPhishing_1_0",
                headers=headers,
                json={"name": "MockPhishing"},
                timeout=10
            )
            self.assertEqual(enable_resp.status_code, 201, f"Failed to activate analyzer: {enable_resp.text}")
            active_mock = enable_resp.json()

        self.assertIsNotNone(active_mock)
        TestStage1BCortex.analyzer_id = active_mock.get("id")
        self.assertTrue(len(TestStage1BCortex.analyzer_id) > 0)

    def test_07_execute_phishing_url_analysis(self):
        """Submit a phishing URL observable to the MockPhishing analyzer and wait for execution."""
        self.assertIsNotNone(TestStage1BCortex.analyst_key)
        self.assertIsNotNone(TestStage1BCortex.analyzer_id)

        headers = {
            "Authorization": f"Bearer {TestStage1BCortex.analyst_key}",
            "Content-Type": "application/json"
        }
        job_payload = {
            "data": "http://evil-phishing-login.example.com/verify",
            "dataType": "url",
            "tlp": 2,
            "message": "Phishing observable automated analysis test"
        }

        job_resp = requests.post(
            f"{BASE_URL}/api/analyzer/{TestStage1BCortex.analyzer_id}/run",
            headers=headers,
            json=job_payload,
            timeout=10
        )
        self.assertEqual(job_resp.status_code, 200, f"Failed to launch analysis job: {job_resp.text}")
        job_data = job_resp.json()
        TestStage1BCortex.job_id = job_data.get("id")
        self.assertIsNotNone(TestStage1BCortex.job_id)

        # Poll job until completion (timeout: 15s)
        final_status = None
        for _ in range(15):
            time.sleep(1)
            poll_resp = requests.get(
                f"{BASE_URL}/api/job/{TestStage1BCortex.job_id}",
                headers={"Authorization": f"Bearer {TestStage1BCortex.analyst_key}"},
                timeout=10
            )
            self.assertEqual(poll_resp.status_code, 200)
            final_status = poll_resp.json().get("status")
            if final_status in ["Success", "Failure"]:
                break

        self.assertEqual(final_status, "Success", f"Job ended with non-success status: {final_status}")

    def test_08_verify_analysis_report_and_verdict(self):
        """Retrieve the analysis report and verify explainable phishing threat intelligence findings."""
        self.assertIsNotNone(TestStage1BCortex.analyst_key)
        self.assertIsNotNone(TestStage1BCortex.job_id)

        report_resp = requests.get(
            f"{BASE_URL}/api/job/{TestStage1BCortex.job_id}/report",
            headers={"Authorization": f"Bearer {TestStage1BCortex.analyst_key}"},
            timeout=10
        )
        self.assertEqual(report_resp.status_code, 200, f"Failed to get report: {report_resp.text}")
        data = report_resp.json()

        self.assertEqual(data.get("status"), "Success")
        self.assertEqual(data.get("dataType"), "url")

        report = data.get("report", {})
        self.assertTrue(report.get("success"), "Analyzer report success flag is False")

        # Validate summary verdict and score
        summary = report.get("summary", {})
        self.assertEqual(summary.get("verdict"), "malicious")
        self.assertEqual(summary.get("score"), 90)

        # Validate detailed threat intelligence taxonomy
        full = report.get("full", {})
        self.assertEqual(full.get("threat_level", full.get("verdict")), "malicious")
        self.assertIn("credential-phishing", full.get("categories", []))
        self.assertTrue(full.get("simulation"))


if __name__ == "__main__":
    unittest.main()
