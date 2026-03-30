import requests

TOKEN = "8043569123:AAHv3MCItdKS2x7qj24wI3wUyuKlPynLvsg"
response = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset=-1")
print(response.json())