#!/usr/bin/env python3
"""
test_stage1a_thehive.py — Automated Component and API Integration Tests for Stage 1A.
Validates TheHive 4.1.24 health, schema status, authentication, organization management,
user provisioning, API key generation, case lifecycle, and observable persistence.
"""

import unittest
import requests
import time
import os

BASE_URL = os.environ.get("THEHIVE_URL", "http://127.0.0.1:9000")
ADMIN_USER = os.environ.get("THEHIVE_ADMIN_USER", "admin@thehive.local")
ADMIN_PASSWORD = os.environ.get("THEHIVE_ADMIN_PASSWORD", "secret")


class TestStage1ATheHive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session = requests.Session()
        cls.api_key = None
        cls.case_id = None
        cls.observable_id = None

    def test_01_health_and_status(self):
        """Verify TheHive API status and JanusGraph database schema version."""
        url = f"{BASE_URL}/api/status"
        resp = self.session.get(url, timeout=10)
        self.assertEqual(resp.status_code, 200, f"Expected 200 OK from status endpoint, got {resp.status_code}")
        data = resp.json()

        # Validate platform versions
        versions = data.get("versions", {})
        self.assertEqual(versions.get("TheHive"), "4.1.24-1", f"Unexpected TheHive version: {versions.get('TheHive')}")

        # Validate database schema
        schema_status = data.get("schemaStatus", [])
        self.assertTrue(len(schema_status) > 0, "No schema status entries found")
        thehive_schema = schema_status[0]
        self.assertEqual(thehive_schema.get("name"), "thehive")
        self.assertEqual(thehive_schema.get("currentVersion"), 99)
        self.assertEqual(thehive_schema.get("expectedVersion"), 99)
        self.assertIsNone(thehive_schema.get("error"))

    def test_02_admin_authentication(self):
        """Verify authentication for the default administrative account."""
        url = f"{BASE_URL}/api/user/current"
        resp = self.session.get(url, auth=(ADMIN_USER, ADMIN_PASSWORD), timeout=10)
        self.assertEqual(resp.status_code, 200, "Admin authentication failed")
        data = resp.json()
        self.assertEqual(data.get("login"), ADMIN_USER)
        self.assertIn("admin", data.get("roles", []))

    def test_03_ensure_soc_organisation(self):
        """Verify or create the SOC tenant organisation for incident handling."""
        # Query existing organisations
        url = f"{BASE_URL}/api/organisation"
        resp = self.session.get(url, auth=(ADMIN_USER, ADMIN_PASSWORD), timeout=10)
        self.assertEqual(resp.status_code, 200)
        orgs = resp.json()
        soc_org = next((o for o in orgs if o.get("name") == "SOC"), None)

        if not soc_org:
            create_resp = self.session.post(
                url,
                auth=(ADMIN_USER, ADMIN_PASSWORD),
                json={"name": "SOC", "description": "Security Operations Center"},
                timeout=10
            )
            self.assertEqual(create_resp.status_code, 201)
            soc_org = create_resp.json()

        self.assertEqual(soc_org.get("name"), "SOC")

    def test_04_ensure_analyst_user_and_api_key(self):
        """Provision a SOAR analyst user in the SOC organisation and generate an API key."""
        user_login = "soar-pipeline@thehive.local"

        # Check if user already exists
        check_resp = self.session.get(
            f"{BASE_URL}/api/v1/user/{user_login}",
            auth=(ADMIN_USER, ADMIN_PASSWORD),
            timeout=10
        )

        if check_resp.status_code == 404:
            # Create user with org-admin profile
            create_resp = self.session.post(
                f"{BASE_URL}/api/v1/user",
                auth=(ADMIN_USER, ADMIN_PASSWORD),
                json={
                    "login": user_login,
                    "name": "SOAR Automation Service",
                    "profile": "org-admin",
                    "organisation": "SOC"
                },
                timeout=10
            )
            self.assertIn(create_resp.status_code, [200, 201], f"Failed to create user: {create_resp.text}")
            time.sleep(1)  # Allow JanusGraph transaction commit

        # Renew/Generate API key
        key_resp = self.session.post(
            f"{BASE_URL}/api/v1/user/{user_login}/key/renew",
            auth=(ADMIN_USER, ADMIN_PASSWORD),
            timeout=10
        )
        self.assertEqual(key_resp.status_code, 200, f"Failed to renew API key: {key_resp.text}")
        api_key = key_resp.text.strip().replace('"', '')
        self.assertTrue(len(api_key) >= 20, "Generated API key is unexpectedly short")
        TestStage1ATheHive.api_key = api_key

    def test_05_create_phishing_case_with_api_key(self):
        """Create a structured phishing incident case using the Bearer API key."""
        self.assertIsNotNone(TestStage1ATheHive.api_key, "API key not available from previous step")

        headers = {
            "Authorization": f"Bearer {TestStage1ATheHive.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "title": "[AUTOMATED TEST] Phishing Alert: Urgent Credential Verification",
            "description": "Synthetic phishing email detected targeting corporate credentials. Observable enrichment pending.",
            "severity": 3,
            "tlp": 2,
            "pap": 2,
            "tags": ["phishing", "stage1a-validation", "credential-theft"]
        }
        resp = self.session.post(f"{BASE_URL}/api/case", headers=headers, json=payload, timeout=10)
        self.assertEqual(resp.status_code, 201, f"Failed to create case: {resp.text}")
        data = resp.json()
        self.assertTrue("_id" in data, "Case response missing _id")
        TestStage1ATheHive.case_id = data["_id"]
        self.assertEqual(data.get("title"), payload["title"])
        self.assertEqual(data.get("status"), "Open")

    def test_06_attach_observables_to_case(self):
        """Attach phishing observables (URL and IP address) to the newly created case."""
        self.assertIsNotNone(TestStage1ATheHive.case_id, "Case ID not available")

        headers = {
            "Authorization": f"Bearer {TestStage1ATheHive.api_key}",
            "Content-Type": "application/json"
        }

        # Observable 1: Phishing URL
        url_payload = {
            "dataType": "url",
            "data": "http://secure-login-update.academic-test.local/verify",
            "message": "Extracted credential harvest link from email body",
            "tlp": 2,
            "ioc": True,
            "tags": ["phishing-url", "synthetic"]
        }
        url_resp = self.session.post(
            f"{BASE_URL}/api/case/{TestStage1ATheHive.case_id}/artifact",
            headers=headers,
            json=url_payload,
            timeout=10
        )
        self.assertEqual(url_resp.status_code, 201, f"Failed to attach URL observable: {url_resp.text}")
        url_data = url_resp.json()
        self.assertTrue(len(url_data) > 0)
        TestStage1ATheHive.observable_id = url_data[0]["_id"]

        # Observable 2: Sender IP
        ip_payload = {
            "dataType": "ip",
            "data": "198.51.100.42",
            "message": "Originating SMTP relay IP from Received headers",
            "tlp": 2,
            "ioc": True,
            "tags": ["sender-ip", "relay"]
        }
        ip_resp = self.session.post(
            f"{BASE_URL}/api/case/{TestStage1ATheHive.case_id}/artifact",
            headers=headers,
            json=ip_payload,
            timeout=10
        )
        self.assertEqual(ip_resp.status_code, 201, f"Failed to attach IP observable: {ip_resp.text}")

    def test_07_retrieve_and_verify_persistence(self):
        """Retrieve the case and observable by ID to confirm persistent storage in Cassandra & Elasticsearch."""
        self.assertIsNotNone(TestStage1ATheHive.case_id)
        self.assertIsNotNone(TestStage1ATheHive.observable_id)

        headers = {"Authorization": f"Bearer {TestStage1ATheHive.api_key}"}

        # Verify Case persistence
        case_resp = self.session.get(f"{BASE_URL}/api/case/{TestStage1ATheHive.case_id}", headers=headers, timeout=10)
        self.assertEqual(case_resp.status_code, 200)
        case_data = case_resp.json()
        self.assertEqual(case_data.get("_id"), TestStage1ATheHive.case_id)
        self.assertIn("stage1a-validation", case_data.get("tags", []))

        # Verify Observable persistence
        obs_resp = self.session.get(f"{BASE_URL}/api/case/artifact/{TestStage1ATheHive.observable_id}", headers=headers, timeout=10)
        self.assertEqual(obs_resp.status_code, 200)
        obs_data = obs_resp.json()
        self.assertEqual(obs_data.get("data"), "http://secure-login-update.academic-test.local/verify")
        self.assertTrue(obs_data.get("ioc"))


if __name__ == "__main__":
    unittest.main()
