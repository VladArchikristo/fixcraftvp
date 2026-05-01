
import requests, sys
TOKEN = sys.argv[1]
CHAT_ID = "244710532"
message = sys.argv[2]
url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
resp = requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})
print(resp.status_code, resp.text)
