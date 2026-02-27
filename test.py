#!/usr/bin/env python3
"""
Network Monitor API - Test Script

This script demonstrates how to interact with the Network Monitor API
and can be used for testing and validation.

Usage:
    python test_api.py
"""

import requests
import json
import time
from datetime import datetime, timedelta
import random

# Configuration
API_BASE_URL = "http://hamza.kainona"
# For local testing, use:
# API_BASE_URL = "http://localhost:8000"

# Test data
TEST_DEVICES = [
    "device-001",
    "device-002",
    "device-003",
    "device-004",
    "device-005"
]

OPERATORS = ["Zong", "Jazz", "Ufone", "Telenor"]
NETWORK_TYPES = ["LTE", "4G", "5G", "3G"]

# Test locations (Pakistan coordinates)
TEST_LOCATIONS = [
    (24.8607, 67.0011),    # Karachi
    (31.5204, 74.3587),    # Lahore
    (34.0837, 72.3222),    # Peshawar
    (33.1849, 60.1676),    # Quetta
    (31.1790, 72.1897),    # Multan
]


def generate_reading(device_id, location_idx=0):
    """Generate a random sensor reading"""
    lat, lon = TEST_LOCATIONS[location_idx % len(TEST_LOCATIONS)]

    # Add small variation to coordinates
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


def test_health():
    """Test health check endpoint"""
    print("\n" + "="*60)
    print("TEST 1: Health Check")
    print("="*60)

    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_single_reading():
    """Test single reading submission"""
    print("\n" + "="*60)
    print("TEST 2: Single Reading Submission")
    print("="*60)

    try:
        reading = generate_reading(TEST_DEVICES[0])
        print(f"Submitting: {json.dumps(reading, indent=2)}")

        response = requests.post(
            f"{API_BASE_URL}/api/network-data",
            json=reading,
            timeout=10
        )
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_batch_readings():
    """Test batch reading submission"""
    print("\n" + "="*60)
    print("TEST 3: Batch Reading Submission (100 readings)")
    print("="*60)

    try:
        # Generate 100 readings
        readings = []
        for i in range(100):
            device_id = TEST_DEVICES[i % len(TEST_DEVICES)]
            reading = generate_reading(device_id, i)
            readings.append(reading)

        batch_payload = {"readings": readings}
        print(f"Submitting {len(readings)} readings...")

        start_time = time.time()
        response = requests.post(
            f"{API_BASE_URL}/api/network-data/batch",
            json=batch_payload,
            timeout=30
        )
        elapsed = time.time() - start_time

        print(f"\nStatus Code: {response.status_code}")
        result = response.json()
        print(f"Response Summary:")
        print(f"  Total Submitted: {result['total_submitted']}")
        print(f"  Successful: {result['successful']}")
        print(f"  Failed: {result['failed']}")
        print(f"  Time Elapsed: {elapsed:.2f}s")
        print(f"  Rate: {result['successful']/elapsed:.0f} readings/sec")

        return response.status_code == 200 and result['successful'] == len(readings)
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_get_all_devices():
    """Test getting all devices"""
    print("\n" + "="*60)
    print("TEST 4: Get All Devices")
    print("="*60)

    try:
        response = requests.get(
            f"{API_BASE_URL}/api/devices",
            timeout=10
        )
        print(f"Status Code: {response.status_code}")
        devices = response.json()
        print(f"Found {len(devices)} device(s):")
        for device in devices:
            print(
                f"  - {device['device_id']}: {device['reading_count']} readings")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_get_device_data():
    """Test retrieving data for specific device"""
    print("\n" + "="*60)
    print("TEST 5: Get Device Data")
    print("="*60)

    try:
        device_id = TEST_DEVICES[0]
        response = requests.get(
            f"{API_BASE_URL}/api/network-data/{device_id}?limit=5&offset=0",
            timeout=10
        )
        print(f"Status Code: {response.status_code}")
        data = response.json()
        print(f"Retrieved {len(data)} reading(s) for {device_id}:")
        for reading in data[:3]:  # Show first 3
            print(
                f"  ID: {reading['id']}, Timestamp: {reading['timestamp']}, Level: {reading['level']}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_large_batch():
    """Test large batch submission (1000 readings)"""
    print("\n" + "="*60)
    print("TEST 6: Large Batch (1000 readings)")
    print("="*60)

    try:
        readings = []
        for i in range(1000):
            device_id = TEST_DEVICES[i % len(TEST_DEVICES)]
            reading = generate_reading(device_id, i)
            readings.append(reading)

        batch_payload = {"readings": readings}
        print(f"Submitting {len(readings)} readings...")

        start_time = time.time()
        response = requests.post(
            f"{API_BASE_URL}/api/network-data/batch",
            json=batch_payload,
            timeout=60
        )
        elapsed = time.time() - start_time

        print(f"\nStatus Code: {response.status_code}")
        result = response.json()
        print(f"Response Summary:")
        print(f"  Total Submitted: {result['total_submitted']}")
        print(f"  Successful: {result['successful']}")
        print(f"  Failed: {result['failed']}")
        print(f"  Time Elapsed: {elapsed:.2f}s")
        print(f"  Rate: {result['successful']/elapsed:.0f} readings/sec")

        return response.status_code == 200 and result['successful'] == len(readings)
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def run_all_tests():
    """Run all tests"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*10 + "Network Monitor API - Test Suite" + " "*15 + "║")
    print("╚" + "="*58 + "╝")
    print(f"\nAPI Base URL: {API_BASE_URL}")

    results = {
        "Health Check": test_health(),
        "Single Reading": test_single_reading(),
        "Batch Readings (100)": test_batch_readings(),
        "Get All Devices": test_get_all_devices(),
        "Get Device Data": test_get_device_data(),
        "Large Batch (1000)": test_large_batch(),
    }

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:<30} {status}")

    print("\n" + "="*60)
    print(f"Results: {passed}/{total} tests passed")
    print("="*60 + "\n")

    return passed == total


if __name__ == "__main__":
    try:
        success = run_all_tests()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user.")
        exit(1)
