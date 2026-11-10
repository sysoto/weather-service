# Weather Service

A standalone microservice that returns the current temperature for any location. Send it a location and a unit, get a temperature back. No API key needed.

---

## Setup

```bash
pip install -r requirements.txt
```

---

## Running the Service

```bash
python3 weather_service.py
```

Leave this running in its own terminal. It listens on `tcp://127.0.0.1:5556` and waits for requests.

---

## Running the Test Client

Open a second terminal while the service is running:

```bash
python3 test_client.py
```

---

## Adding This to Your Program

You need two things: the `pyzmq` library installed, and the service running in a separate terminal.

**Step 1 — Install the library (one time)**

```bash
pip install pyzmq
```

**Step 2 — Copy this helper function into your program**

```python
import json
import zmq

def get_temperature(location, unit):
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.RCVTIMEO, 5000)  # wait up to 5 seconds
    socket.connect("tcp://127.0.0.1:5556")

    socket.send_string(json.dumps({
        "action": "get_temperature",
        "location": location,
        "unit": unit
    }))

    try:
        response = json.loads(socket.recv())
    except zmq.Again:
        response = {"success": False, "error": "Weather service is not running."}

    socket.close()
    context.term()
    return response
```

**Step 3 — Call it wherever you need the temperature**

Every program is different, so there's no single right place to add this. Just find a spot in your code where you already have a location name and want to show the weather alongside it. Then call `get_temperature` with that location and display what comes back.

Here's the basic pattern:

```python
response = get_temperature("Portland, OR", "F")

if response["success"]:
    print(f"{response['location']}: {response['temperature']} {response['unit']}")
else:
    print(f"Could not get weather: {response['error']}")
```

If the service isn't running, `response["success"]` will be `False` and your program will just skip the weather — it won't crash.

That's it. The service runs separately — your program just sends a request and reads the response.

---

## Request Format

Send a JSON object with these three fields:

| Field      | Required | Description                             |
| ---------- | -------- | --------------------------------------- |
| `action`   | Yes      | Always `"get_temperature"`              |
| `location` | Yes      | City name, e.g. `"Washington, DC"`      |
| `unit`     | Yes      | `"F"` for Fahrenheit, `"C"` for Celsius |

## Response Format

**Success**

```json
{
  "success": true,
  "location": "Washington, DC",
  "temperature": 64.2,
  "unit": "F"
}
```

**Error**

```json
{
  "success": false,
  "error": "Location was not found."
}
```

Always check `response["success"]` before using `response["temperature"]`.
