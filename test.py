#!/usr/bin/env python3
"""
Network Monitor API - Debug Test Suite
More detailed testing with better error reporting
"""

import requests
import json
import time
from datetime import datetime, timedelta
import random
from typing import Dict, Any

# Configuration
API_BASE_URL = "http://localhost:8000"
# API_BASE_URL = "http://hamza.kainona.com"

TEST_DEVICES = ["device-001", "device-002", "device-003"]
OPERATORS = ["Zong", "Jazz", "Ufone", "Telenor"]
NETWORK_TYPES = ["LTE", "4G", "5G", "3G"]
TEST_LOCATIONS = [
    (24.8607, 67.0011),
    (31.5204, 74.3587),
    (34.0837, 72.3222),
]


def print_section(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_test(name: str, status: bool, details: str = ""):
    icon = "✅" if status else "❌"
    print(f"\n{icon} {name}")
    if details:
        print(f"   {details}")


def print_request_debug(method: str, url: str, payload: Any = None):
    print(f"\n📤 Request: {method} {url}")
    if payload:
        if isinstance(payload, dict):
            print(f"   Payload: {json.dumps(payload, indent=2)[:200]}...")
        else:
            print(f"   Payload size: {len(str(payload))} bytes")


def print_response_debug(response: requests.Response):
    print(f"\n📥 Response:")
    print(f"   Status: {response.status_code}")
    try:
        data = response.json()
        print(f"   Body: {json.dumps(data, indent=2)[:500]}")
        if len(json.dumps(data)) > 500:
            print("   [truncated...]")
    except:
        print(f"   Body: {response.text[:200]}")


def generate_reading(device_id: str, idx: int = 0) -> Dict:
    lat, lon = TEST_LOCATIONS[idx % len(TEST_LOCATIONS)]
    lat += random.uniform(-0.01, 0.01)
    lon += random.uniform(-0.01, 0.01)

    return {
        "deviceId": device_id,
        "timestamp": (datetime.utcnow() - timedelta(minutes=random.randint(0, 60))).isoformat() + "Z",
        "latitude": lat,
        "longitude": lon,
        "level": random.randint(0, 31),
        "asu": random.randint(0, 31),
        "rsrp": random.randint(-130, -50),
        "rssi": random.randint(-120, -25),
        "dbm": random.randint(-130, -50),
        "rsrq": random.randint(-30, 0),
        "networkType": random.choice(NETWORK_TYPES),
        "operator": random.choice(OPERATORS),
        "cellId": f"cell-{random.randint(10000, 99999)}",
        "physicalCellId": random.randint(0, 503),
        "trackingAreaCode": random.randint(1000, 9999)
    }


# ============================================================================
# TEST SUITE
# ============================================================================

def test_root():
    """Test root endpoint"""
    print_section("TEST 1: Root Endpoint")
    try:
        print_request_debug("GET", f"{API_BASE_URL}/")
        response = requests.get(f"{API_BASE_URL}/", timeout=10)
        print_response_debug(response)
        status = response.status_code == 200
        print_test("Root Endpoint", status)
        return status
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def test_health():
    """Test health check"""
    print_section("TEST 2: Health Check")
    try:
        print_request_debug("GET", f"{API_BASE_URL}/health")
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        print_response_debug(response)
        status = response.status_code == 200
        has_db = response.json().get("database") == "connected" if status else False
        print_test("Health Check", status,
                   f"Database: {'connected' if has_db else 'FAILED'}")
        return status and has_db
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def test_single_reading():
    """Test single reading submission"""
    print_section("TEST 3: Single Reading Submission")
    try:
        reading = generate_reading(TEST_DEVICES[0])
        print_request_debug(
            "POST", f"{API_BASE_URL}/api/network-data", reading)

        response = requests.post(
            f"{API_BASE_URL}/api/network-data",
            json=reading,
            timeout=10
        )
        print_response_debug(response)

        status = response.status_code == 200
        has_id = response.json().get("id") is not None if status else False
        print_test("Single Reading", status,
                   f"Saved ID: {response.json().get('id') if has_id else 'MISSING'}")
        return status and has_id
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def test_single_reading_invalid():
    """Test invalid reading (missing required field)"""
    print_section("TEST 4: Invalid Reading (Validation)")
    try:
        reading = {"timestamp": datetime.utcnow().isoformat()
                   }  # Missing deviceId
        print_request_debug(
            "POST", f"{API_BASE_URL}/api/network-data", reading)

        response = requests.post(
            f"{API_BASE_URL}/api/network-data",
            json=reading,
            timeout=10
        )
        print_response_debug(response)

        status = response.status_code == 422  # Validation error expected
        print_test("Validation Rejection", status,
                   f"Got status {response.status_code}")
        return status
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def test_batch_small():
    """Test batch with 10 readings"""
    print_section("TEST 5: Batch - Small (10 readings)")
    try:
        readings = [generate_reading(
            TEST_DEVICES[i % len(TEST_DEVICES)], i) for i in range(10)]
        payload = {"readings": readings}

        print_request_debug(
            "POST", f"{API_BASE_URL}/api/network-data/batch", payload)

        start = time.time()
        response = requests.post(
            f"{API_BASE_URL}/api/network-data/batch",
            json=payload,
            timeout=30
        )
        elapsed = time.time() - start
        print_response_debug(response)

        status = response.status_code == 200
        result = response.json() if status else {}

        summary = f"Successful: {result.get('successful', 'N/A')}/{result.get('total_submitted', 'N/A')}, Time: {elapsed:.2f}s"
        print_test("Batch Small", status, summary)

        if status and result.get('failed', 0) > 0:
            print(f"\n   ⚠️  Failed items details:")
            for detail in result.get('details', []):
                if detail.get('status') == 'failed':
                    print(
                        f"      - Index {detail.get('index')}: {detail.get('error')}")

        return status and result.get('successful') == 10
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def test_batch_medium():
    """Test batch with 100 readings"""
    print_section("TEST 6: Batch - Medium (100 readings)")
    try:
        readings = [generate_reading(
            TEST_DEVICES[i % len(TEST_DEVICES)], i) for i in range(100)]
        payload = {"readings": readings}

        print(f"📤 Request: POST {API_BASE_URL}/api/network-data/batch")
        print(f"   Payload size: {len(json.dumps(payload))} bytes")

        start = time.time()
        response = requests.post(
            f"{API_BASE_URL}/api/network-data/batch",
            json=payload,
            timeout=30
        )
        elapsed = time.time() - start
        print_response_debug(response)

        status = response.status_code == 200
        result = response.json() if status else {}

        rate = result.get('successful', 0) / elapsed if elapsed > 0 else 0
        summary = f"Successful: {result.get('successful', 'N/A')}/{result.get('total_submitted', 'N/A')}, Time: {elapsed:.2f}s, Rate: {rate:.0f}/sec"
        print_test("Batch Medium", status, summary)

        if status and result.get('failed', 0) > 0:
            print(
                f"\n   ⚠️  {result.get('failed')} failed items (showing first 3):")
            for detail in result.get('details', [])[:3]:
                if detail.get('status') == 'failed':
                    print(
                        f"      - Index {detail.get('index')}: {detail.get('error')}")

        return status and result.get('successful') == 100
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def test_batch_large():
    """Test batch with 500 readings"""
    print_section("TEST 7: Batch - Large (500 readings)")
    try:
        readings = [generate_reading(
            TEST_DEVICES[i % len(TEST_DEVICES)], i) for i in range(500)]
        payload = {"readings": readings}

        print(f"📤 Request: POST {API_BASE_URL}/api/network-data/batch")
        print(f"   Payload size: {len(json.dumps(payload))} bytes")

        start = time.time()
        response = requests.post(
            f"{API_BASE_URL}/api/network-data/batch",
            json=payload,
            timeout=60
        )
        elapsed = time.time() - start
        print_response_debug(response)

        status = response.status_code == 200
        result = response.json() if status else {}

        rate = result.get('successful', 0) / elapsed if elapsed > 0 else 0
        summary = f"Successful: {result.get('successful', 'N/A')}/{result.get('total_submitted', 'N/A')}, Time: {elapsed:.2f}s, Rate: {rate:.0f}/sec"
        print_test("Batch Large", status, summary)

        if status and result.get('failed', 0) > 0:
            print(f"\n   ⚠️  {result.get('failed')} failed items")

        return status and result.get('successful') == 500
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def test_get_all_devices():
    """Test getting all devices"""
    print_section("TEST 8: Get All Devices")
    try:
        print_request_debug("GET", f"{API_BASE_URL}/api/devices")
        response = requests.get(f"{API_BASE_URL}/api/devices", timeout=10)
        print_response_debug(response)

        status = response.status_code == 200
        devices = response.json() if status else []
        summary = f"Found {len(devices)} device(s)"
        print_test("Get All Devices", status, summary)

        if devices:
            for device in devices[:3]:
                print(
                    f"   - {device.get('device_id')}: {device.get('reading_count')} readings")
            if len(devices) > 3:
                print(f"   ... and {len(devices)-3} more")

        return status and len(devices) > 0
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def test_get_device_data():
    """Test getting data for a specific device"""
    print_section("TEST 9: Get Device Data")
    try:
        device_id = TEST_DEVICES[0]
        url = f"{API_BASE_URL}/api/network-data/{device_id}?limit=5&offset=0"
        print_request_debug("GET", url)
        response = requests.get(url, timeout=10)
        print_response_debug(response)

        status = response.status_code == 200
        data = response.json() if status else []
        summary = f"Retrieved {len(data)} reading(s) for {device_id}"
        print_test("Get Device Data", status, summary)

        if data:
            for reading in data[:2]:
                print(
                    f"   - ID: {reading.get('id')}, Level: {reading.get('level')}, RSRP: {reading.get('rsrp')}")

        return status and len(data) > 0
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def test_batch_with_invalid():
    """Test batch with mix of valid and invalid readings"""
    print_section("TEST 10: Batch - Mixed Valid/Invalid")
    try:
        readings = []
        # Add 5 valid readings
        for i in range(5):
            readings.append(generate_reading(
                TEST_DEVICES[i % len(TEST_DEVICES)], i))
        # Add invalid reading (missing deviceId)
        readings.append({"timestamp": datetime.utcnow().isoformat()})
        # Add more valid readings
        for i in range(5, 10):
            readings.append(generate_reading(
                TEST_DEVICES[i % len(TEST_DEVICES)], i))

        payload = {"readings": readings}
        print(f"📤 Request: POST {API_BASE_URL}/api/network-data/batch")
        print(f"   Total readings: {len(readings)} (1 invalid expected)")

        response = requests.post(
            f"{API_BASE_URL}/api/network-data/batch",
            json=payload,
            timeout=30
        )
        print_response_debug(response)

        status = response.status_code == 200
        result = response.json() if status else {}

        summary = f"Successful: {result.get('successful')}, Failed: {result.get('failed')}"
        print_test("Batch Mixed", status, summary)

        if result.get('failed', 0) > 0:
            print(f"\n   Failed items:")
            for detail in result.get('details', []):
                if detail.get('status') == 'failed':
                    print(
                        f"      - Index {detail.get('index')}: {detail.get('error')}")

        return status and result.get('failed') >= 1
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


# ============================================================================
# MAIN
# ============================================================================

def run_all_tests():
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*12 + "Network Monitor API - Debug Test Suite" + " "*18 + "║")
    print("╚" + "="*68 + "╝")
    print(f"\nAPI Base URL: {API_BASE_URL}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}")

    tests = [
        ("Root Endpoint", test_root),
        ("Health Check", test_health),
        ("Single Reading", test_single_reading),
        ("Invalid Reading", test_single_reading_invalid),
        ("Batch Small (10)", test_batch_small),
        ("Batch Medium (100)", test_batch_medium),
        ("Batch Large (500)", test_batch_large),
        ("Get All Devices", test_get_all_devices),
        ("Get Device Data", test_get_device_data),
        ("Batch Mixed", test_batch_with_invalid),
    ]

    results = {}
    for test_name, test_func in tests:
        results[test_name] = test_func()

    # Summary
    print_section("TEST SUMMARY")
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name:<40} {status}")

    print(f"\n  Overall: {passed}/{total} tests passed")
    print("="*70 + "\n")

    return passed == total


if __name__ == "__main__":
    try:
        success = run_all_tests()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests interrupted.")
        exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        exit(1)
