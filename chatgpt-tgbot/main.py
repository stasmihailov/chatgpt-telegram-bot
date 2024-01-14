import contextlib
import datetime
import os
import random
from enum import Enum
from typing import Dict

import openai
import requests
from openai import BadRequestError
from openai import OpenAI
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import Choice


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
client = OpenAI(api_key= openai.api_key)

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
        except BadRequestError as e:
            print(e)
            return None, str(e)
        except Exception as e:
            print(e)
            return None, 'Internal server error'

        images = [data['url'] for data in response['data']]
        print({**ctx, 'query': query, 'images': images})
        return images, None

    @staticmethod
    def generate_text(query, **ctx):
        if not ctx:
            ctx = {}

        try:
            response: ChatCompletion = client.chat.completions.create(
                model='gpt-4',
                # stream=True,
                messages=[
                    message(Role.USER, query)
                ]
            )
        except BadRequestError as e:
            print(e)
            return None, str(e)
        except Exception as e:
            print(e)
            return None, 'Something went wrong, please try again later'

        print({**ctx, 'response': response})

        first_choice = response.choices[0]
        # verify message stop reason here
        # first_choice.finish_reason == Choice.

        return first_choice.message.content, None

    @staticmethod
    def get_remaining_credit():
        try:
            resp = requests.get('https://api.openai.com/dashboard/billing/credit_grants', headers={
                'Authorization': f'Bearer {openai.api_key}'
            }).json()
        except BadRequestError as e:
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


class Role(Enum):
    SYSTEM = 'system'
    USER = 'user'


def message(role: Role, content: str) -> Dict:
    return {
        'role': str(role.value),
        'content': content
    }


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
        text, err = Requests.generate_text(query, ctx={'chat_id': chat_id})
        if err:
            Responses.send_message(chat_id, err)
            return

        Responses.send_message(chat_id, text)


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
