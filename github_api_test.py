import requests

url = "https://api.github.com"

response = requests.get(url)

print("Status code:", response.status_code)

data = response.json()

print("Current user URL:", data["current_user_url"])
print("Events URL:", data["events_url"])
print("Emojis URL:", data["emojis_url"])
