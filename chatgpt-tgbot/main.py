import contextlib
import datetime
import os
import random

import openai
import requests
from openai import InvalidRequestError


def getenv(key):
    keys = {
        "OPENAI_API_KEY": 'key for accessing dalle api',
        "TG_TOKEN": 'telegram bot token',
    }
    if key not in keys.keys():
        raise f'cannot find key {key} in keys {keys.keys()}'

    return os.getenv(key)


openai.api_key = getenv("OPENAI_API_KEY")
tg_token = getenv("TG_TOKEN")

rand = random.Random()
img_price = 0.02


class Requests:
    @staticmethod
    def generate(query, **ctx):
        if not ctx:
            ctx = {}

        try:
            response = openai.Image.create(
                prompt=query,
                n=1,
                size="1024x1024"
            )
        except InvalidRequestError as e:
            print(e)
            return None, str(e)
        except Exception as e:
            print(e)
            return None, 'Internal server error'

        images = [data['url'] for data in response['data']]
        print({**ctx, 'query': query, 'images': images})
        return images, None

    @staticmethod
    def get_remaining_credit():
        try:
            resp = requests.get('https://api.openai.com/dashboard/billing/credit_grants', headers={
                'Authorization': f'Bearer {openai.api_key}'
            }).json()
        except InvalidRequestError as e:
            print(e)
            return None, None, str(e)
        except Exception as e:
            print(e)
            return None, None, 'Internal server error'
        if 'grants' not in resp:
            return None, None, 'Internal server error'

        grant = resp['grants']['data'][0]

        token_sum = grant['grant_amount'] - grant['used_amount']
        tokens = int(token_sum / img_price)

        expiration_seconds = int(grant['expires_at'])
        expiration = datetime.datetime.fromtimestamp(expiration_seconds).strftime('%B %-d, %Y')

        return tokens, expiration, None


class Responses:
    @staticmethod
    @contextlib.contextmanager
    def pretend_typing(chat_id):
        url = f'https://api.telegram.org/bot{tg_token}/sendChatAction'
        requests.post(url, json={
            'chat_id': chat_id,
            'action': 'typing',
        })
        yield

    @staticmethod
    def send_photo(chat_id, image):
        url = f'https://api.telegram.org/bot{tg_token}/sendPhoto'
        payload = {
            'chat_id': chat_id,
            'photo': image,
        }

        requests.post(url, json=payload)

    @staticmethod
    def send_message(chat_id, text):
        url = f'https://api.telegram.org/bot{tg_token}/sendMessage'
        payload = {
            'chat_id': chat_id,
            'text': text,
        }

        requests.post(url, json=payload)


def generate_response(request):
    msg = request.get_json()

    try:
        if 'message' in msg and 'text' in msg['message']:
            respond_message(msg)
    finally:
        pass

    return 'ok'


def respond_message(msg):
    query = msg['message']['text']
    chat_id = msg['message']['chat']['id']

    if query.startswith('/'):
        respond_command(chat_id, query)
        return

    with Responses.pretend_typing(chat_id):
        images, err = Requests.generate(query, ctx={'chat_id': chat_id})
        if err:
            Responses.send_message(chat_id, err)
            return

        for idx, image in enumerate(images):
            Responses.send_photo(chat_id, image)


def respond_command(chat_id, query):
    if query == '/start' or query == '/help':
        with Responses.pretend_typing(chat_id):
            Responses.send_message(chat_id, "Start by sending a message - for example, 'What can this bot do?'")
    elif query == '/tokens':
        with Responses.pretend_typing(chat_id):
            tokens, expiration, err = Requests.get_remaining_credit()
            if err:
                Responses.send_message(chat_id, err)
                return

            Responses.send_message(chat_id, f"You have {tokens} remaining token(s) to spend "
                                            f"until {expiration}")
