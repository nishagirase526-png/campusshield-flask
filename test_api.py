import urllib.request
import json

print("Test 1: GET /api/colleges")
try:
    response = urllib.request.urlopen('http://127.0.0.1:5000/api/colleges')
    data = json.loads(response.read().decode('utf-8'))
    print(f"Status Code: {response.status}")
    print(f"Number of colleges returned: {len(data)}")
except Exception as e:
    print(f"Error: {e}")

print("\nTest 2: Invalid college_id registration rejection")
try:
    data = json.dumps({
        "name": "Test User",
        "registerMethod": "email",
        "identifier": "test@example.com",
        "password": "password123",
        "confirmPassword": "password123",
        "college_id": 9999  # Invalid college_id
    }).encode('utf-8')
    
    req = urllib.request.Request(
        'http://127.0.0.1:5000/api/register',
        data=data,
        headers={'Content-Type': 'application/json'}
    )
    
    response = urllib.request.urlopen(req)
    result = json.loads(response.read().decode('utf-8'))
    print(f"Status Code: {response.status}")
    print(f"Response: {result}")
except urllib.error.HTTPError as e:
    error_data = json.loads(e.read().decode('utf-8'))
    print(f"Status Code: {e.code}")
    print(f"Response: {error_data}")
except Exception as e:
    print(f"Error: {e}")
