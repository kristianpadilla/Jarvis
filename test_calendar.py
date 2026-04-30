import requests

# Add test event
r = requests.post("http://localhost:5000/calendar/add", json={
    "date": "4/28/2026",
    "time": "09:00",
    "title": "Test Calendar Event"
})
print("Added:", r.json())
