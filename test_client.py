"""
Test client for the Weather Microservice.
Run weather_service.py in a separate terminal first, then run this file.
"""

import json
import zmq

ENDPOINT = "tcp://127.0.0.1:5556"


def send_request(socket, payload):
    """Send a raw string and return the parsed JSON response."""
    socket.send_string(payload)
    try:
        return json.loads(socket.recv())
    except zmq.Again:
        return {"success": False, "error": "Service did not respond."}


def make_socket(context):
    sock = context.socket(zmq.REQ)
    sock.setsockopt(zmq.RCVTIMEO, 5000)
    sock.connect(ENDPOINT)
    return sock


def run_tests():
    context = zmq.Context()

    test_cases = [
        # (label, raw payload string)
        (
            "1. Washington, DC in Fahrenheit",
            json.dumps({"action": "get_temperature", "location": "Washington, DC", "unit": "F"}),
        ),
        (
            "2. Washington, DC in Celsius",
            json.dumps({"action": "get_temperature", "location": "Washington, DC", "unit": "C"}),
        ),
        (
            "3. Invalid temperature unit",
            json.dumps({"action": "get_temperature", "location": "Washington, DC", "unit": "X"}),
        ),
        (
            "4. Missing location",
            json.dumps({"action": "get_temperature", "location": "", "unit": "F"}),
        ),
        (
            "5. Location that does not exist",
            json.dumps({"action": "get_temperature", "location": "Zzznotaplace123", "unit": "F"}),
        ),
        (
            "6. Unknown action",
            json.dumps({"action": "get_forecast", "location": "Washington, DC", "unit": "F"}),
        ),
        (
            "7. Malformed JSON",
            "this is not json",
        ),
    ]

    print("=" * 60)
    print("Weather Service — Functional Tests")
    print("=" * 60)

    for label, payload in test_cases:
        sock = make_socket(context)
        response = send_request(sock, payload)
        sock.close()

        print(f"\n{label}")
        print(f"  Sent:     {payload}")
        print(f"  Received: {json.dumps(response)}")

    # Reliability test: 100 consecutive requests
    print("\n" + "=" * 60)
    print("Reliability Test — 100 consecutive requests")
    print("=" * 60)

    import random
    valid = {"action": "get_temperature", "location": "Tokyo", "unit": "C"}
    invalid = {"action": "get_temperature", "location": "", "unit": "F"}
    passed = 0

    for i in range(100):
        payload = json.dumps(valid if i % 3 != 0 else invalid)
        sock = make_socket(context)
        response = send_request(sock, payload)
        sock.close()
        if "success" in response:
            passed += 1

    print(f"\n  Responses received: {passed}/100")
    if passed == 100:
        print("  PASSED — service responded to all 100 requests.")
    else:
        print(f"  FAILED — {100 - passed} request(s) did not get a valid response.")

    context.term()


if __name__ == "__main__":
    run_tests()
