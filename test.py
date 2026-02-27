#!/usr/bin/env python3
"""
Comprehensive API Testing Script for Network Monitor API
Usage: python test_api.py [base_url]
Example: python test_api.py http://localhost:8000
"""

import requests
import json
import sys
from datetime import datetime
from typing import Optional


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


class APITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.passed = 0
        self.failed = 0

    def log_success(self, message: str):
        print(f"{Colors.GREEN}✓ {message}{Colors.END}")
        self.passed += 1

    def log_error(self, message: str):
        print(f"{Colors.RED}✗ {message}{Colors.END}")
        self.failed += 1

    def log_info(self, message: str):
        print(f"{Colors.BLUE}ℹ {message}{Colors.END}")

    def log_warning(self, message: str):
        print(f"{Colors.YELLOW}⚠ {message}{Colors.END}")

    def test_health(self):
        """Test health endpoint"""
        print("\n" + "="*50)
        print("Testing Health Endpoint")
        print("="*50)

        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)

            if response.status_code == 200:
                data = response.json()
                self.log_success(
                    f"Health check passed: {response.status_code}")
                print(f"   Response: {json.dumps(data, indent=2)}")

                if data.get("status") == "healthy":
                    self.log_success("Database connection is healthy")
                else:
                    self.log_warning("Service is running but may have issues")
            else:
                self.log_error(f"Health check failed: {response.status_code}")

        except requests.exceptions.ConnectionError:
            self.log_error("Cannot connect to API. Is the server running?")
        except Exception as e:
            self.log_error(f"Health check error: {str(e)}")

    def test_root(self):
        """Test root endpoint"""
        print("\n" + "="*50)
        print("Testing Root Endpoint")
        print("="*50)

        try:
            response = requests.get(f"{self.base_url}/", timeout=5)

            if response.status_code == 200:
                self.log_success(
                    f"Root endpoint accessible: {response.status_code}")
                print(f"   Response: {json.dumps(response.json(), indent=2)}")
            else:
                self.log_error(f"Root endpoint failed: {response.status_code}")

        except Exception as e:
            self.log_error(f"Root endpoint error: {str(e)}")

    def test_post_data(self) -> Optional[str]:
        """Test POST network data"""
        print("\n" + "="*50)
        print("Testing POST /api/network-data")
        print("="*50)

        test_data = {
            "deviceId": f"test_device_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "latitude": 30.0444,
            "longitude": 31.2357,
            "level": -75,
            "asu": 20,
            "rsrp": -95,
            "rssi": -65,
            "dbm": -75,
            "rsrq": -10,
            "networkType": "LTE",
            "operator": "Vodafone Egypt",
            "cellId": "12345",
            "physicalCellId": 100,
            "trackingAreaCode": 200
        }

        try:
            self.log_info(f"Sending data for device: {test_data['deviceId']}")
            response = requests.post(
                f"{self.base_url}/api/network-data",
                json=test_data,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                self.log_success(
                    f"Data posted successfully: {response.status_code}")
                print(f"   Response: {json.dumps(data, indent=2)}")
                return test_data['deviceId']
            else:
                self.log_error(f"POST failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return None

        except Exception as e:
            self.log_error(f"POST error: {str(e)}")
            return None

    def test_get_device_data(self, device_id: str):
        """Test GET device data"""
        print("\n" + "="*50)
        print(f"Testing GET /api/network-data/{device_id}")
        print("="*50)

        try:
            response = requests.get(
                f"{self.base_url}/api/network-data/{device_id}",
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                self.log_success(f"Retrieved {len(data)} readings")

                if data:
                    print(f"   Latest reading:")
                    print(f"   {json.dumps(data[0], indent=2)}")
                else:
                    self.log_warning("No readings found for this device")
            else:
                self.log_error(f"GET failed: {response.status_code}")

        except Exception as e:
            self.log_error(f"GET error: {str(e)}")

    def test_get_all_devices(self):
        """Test GET all devices"""
        print("\n" + "="*50)
        print("Testing GET /api/devices")
        print("="*50)

        try:
            response = requests.get(f"{self.base_url}/api/devices", timeout=10)

            if response.status_code == 200:
                data = response.json()
                self.log_success(f"Retrieved {len(data)} devices")

                if data:
                    print(f"   Devices:")
                    for device in data[:5]:  # Show first 5
                        print(
                            f"   - {device['device_id']}: {device['reading_count']} readings")

                    if len(data) > 5:
                        print(f"   ... and {len(data) - 5} more")
                else:
                    self.log_warning("No devices found in database")
            else:
                self.log_error(f"GET failed: {response.status_code}")

        except Exception as e:
            self.log_error(f"GET error: {str(e)}")

    def test_invalid_data(self):
        """Test validation with invalid data"""
        print("\n" + "="*50)
        print("Testing Data Validation")
        print("="*50)

        invalid_data = {
            "deviceId": "",  # Empty device ID
            "latitude": 999  # Invalid latitude
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/network-data",
                json=invalid_data,
                timeout=10
            )

            if response.status_code == 422:
                self.log_success("Validation correctly rejected invalid data")
            else:
                self.log_error(
                    f"Unexpected response for invalid data: {response.status_code}")

        except Exception as e:
            self.log_error(f"Validation test error: {str(e)}")

    def test_pagination(self):
        """Test pagination parameters"""
        print("\n" + "="*50)
        print("Testing Pagination")
        print("="*50)

        try:
            # Test with limit
            response = requests.get(
                f"{self.base_url}/api/devices",
                timeout=10
            )

            if response.status_code == 200 and response.json():
                device_id = response.json()[0]['device_id']

                # Test with different limits
                for limit in [5, 10]:
                    resp = requests.get(
                        f"{self.base_url}/api/network-data/{device_id}",
                        params={"limit": limit},
                        timeout=10
                    )

                    if resp.status_code == 200:
                        count = len(resp.json())
                        self.log_success(
                            f"Pagination limit={limit} returned {count} items")
                    else:
                        self.log_error(
                            f"Pagination test failed for limit={limit}")
            else:
                self.log_warning("No devices available for pagination test")

        except Exception as e:
            self.log_error(f"Pagination test error: {str(e)}")

    def run_all_tests(self):
        """Run all tests"""
        print(f"\n{Colors.BLUE}{'='*50}")
        print(f"Starting API Tests")
        print(f"Base URL: {self.base_url}")
        print(f"{'='*50}{Colors.END}\n")

        # Run tests
        self.test_health()
        self.test_root()
        device_id = self.test_post_data()

        if device_id:
            self.test_get_device_data(device_id)

        self.test_get_all_devices()
        self.test_invalid_data()
        self.test_pagination()

        # Summary
        print(f"\n{Colors.BLUE}{'='*50}")
        print("Test Summary")
        print(f"{'='*50}{Colors.END}")
        print(f"{Colors.GREEN}Passed: {self.passed}{Colors.END}")
        print(f"{Colors.RED}Failed: {self.failed}{Colors.END}")

        if self.failed == 0:
            print(f"\n{Colors.GREEN}🎉 All tests passed!{Colors.END}\n")
        else:
            print(
                f"\n{Colors.RED}⚠️  Some tests failed. Please review the output above.{Colors.END}\n")


def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

    tester = APITester(base_url)
    tester.run_all_tests()


if __name__ == "__main__":
    main()
