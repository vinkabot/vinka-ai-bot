import requests
import json
from datetime import datetime

url = "https://api.github.com/events"

response = requests.get(url)

if response.status_code == 200:
    data = response.json()

    filename = "github_events.json"

    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)

    print("Data saved successfully!")
    print("Events count:", len(data))
    print("Saved at:", datetime.now())

else:
    print("Error:", response.status_code)
