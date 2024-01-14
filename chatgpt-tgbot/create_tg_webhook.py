import os

import requests

if __name__ == '__main__':
    tg_token = os.getenv("TG_TOKEN")
    webhook = os.getenv("GCLOUD_WEBHOOK_URL")

    url = f'https://api.telegram.org/bot{tg_token}/setWebhook?url={webhook}'
    requests.post(url)
