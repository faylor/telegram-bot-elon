import os
import logging
import requests
import json
from aiogram import Bot, types
from requests import Response
import asyncio
from bot.settings import (TELEGRAM_BOT)

def fire_and_forget(f):
    def wrapped(*args, **kwargs):
        return asyncio.get_event_loop().run_in_executor(None, f, *args, *kwargs)
    return wrapped

@fire_and_forget
def get_stream(twits):
    try:
        if twits.stream is None:
            twits.start_stream()
        for response_line in twits.stream:
            if response_line and len(twits.chat_ids) > 0:
                json_response = json.loads(response_line)
                for chat_id in twits.chat_ids:
                    logging.warn("SENDING Line ++" + str(chat_id))
                    text = "\n YO! WAKE UP. \n\n WAAAAKKKKKEEE UP \n\n Got A Tweet: " + json_response["data"]["text"]
                    bot_key = TELEGRAM_BOT
                    send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
                    resp = requests.post(send_message_url)
                    logging.warn("SENT Line +RESP+" + str(resp.status_code))
                    logging.warn("SENT Line +RESP text+" + str(resp.text))
                    
                    logging.warn("SENT Line ++" + str(chat_id))
                logging.warn(json.dumps(json_response, indent=4, sort_keys=True))
    except Exception as e:
        logging.error("STREAM ERROR:" + str(e))



class Twits:

    def __init__(self):
        bearer_token = os.environ["TWITTER_ACCESS_TOKEN"]
        self.headers = {"Authorization": "Bearer {}".format(bearer_token)}
        self.twitter_search_url = "https://api.twitter.com/2/tweets/search/recent?query={}&{}"
        self.twitter_stream_url = "https://api.twitter.com/2/tweets/search/stream"
        self.chat_ids = [1442973965,-375104421,1038547988]
        self.stream: Response = None
    
    def close(self):
        self.stream.close()

    def search_twitter(self, query, tweet_fields):    
        headers = {"Authorization": "Bearer {}".format(self.bearer_token)}
        url = self.twitter_search_url.format(query, tweet_fields)    
        response = requests.request("GET", url, headers=headers)
        print(response.status_code)

        if response.status_code != 200:
            raise Exception(response.status_code, response.text)
        return response.json()

    def prepare_stream(self):
        rules = self.get_stream_rules()
        self.delete_stream_all_rules(rules)
        self.set_stream_rules()
        
    def add_chat_id(self, chat_id):
        if chat_id not in self.chat_ids:
            self.chat_ids.append(chat_id)
            logging.warn("Added CHAT ID:" + str(chat_id))

    def remove_chat_id(self, chat_id):
        if chat_id in self.chat_ids:
            self.chat_ids.remove(chat_id)

    def get_stream_rules(self):
        response = requests.get(self.twitter_stream_url + "/rules", headers=self.headers)
        if response.status_code != 200:
            raise Exception(
                "Cannot get rules (HTTP {}): {}".format(response.status_code, response.text)
            )
        print(json.dumps(response.json()))
        return response.json()

    def delete_stream_all_rules(self, rules):
        if rules is None or "data" not in rules:
            return None

        ids = list(map(lambda rule: rule["id"], rules["data"]))
        payload = {"delete": {"ids": ids}}
        response = requests.post(self.twitter_stream_url + "/rules", headers=self.headers, json=payload)
        if response.status_code != 200:
            raise Exception(
                "Cannot delete rules (HTTP {}): {}".format(
                    response.status_code, response.text
                )
            )
        print(json.dumps(response.json()))


    def set_stream_rules(self):
        # You can adjust the rules if needed
        sample_rules = [
            {"value": "from:elonmusk", "tag": "doge 5dog12"},
            {"value": "from:CryptoDonAlt", "tag": "CryptoDonAlt"},
            {"value": "from:100trillionUSD", "tag": "100trillionUSD"},
            {"value": "bitcoin from:NickSzabo4", "tag": "NickSzabo4"}
        ]
        payload = {"add": sample_rules}
        response = requests.post(self.twitter_stream_url + "/rules", headers=self.headers, json=payload)
        if response.status_code != 201:
            raise Exception(
                "Cannot add rules (HTTP {}): {}".format(response.status_code, response.text)
            )
        print(json.dumps(response.json()))

    def start_stream(self):
        try:
            if self.stream is None:
                logging.warn("-- OPENING STREAM ---")
                response = requests.get(self.twitter_stream_url, headers=self.headers, stream=True)
                logging.warn("STREAM RESP:" + str(response.status_code))
                if response.status_code != 200:
                    raise Exception(
                        "Cannot get stream (HTTP {}): {}".format(
                            response.status_code, response.text
                        )
                    )
                self.stream = response.iter_lines()
        except Exception as e:
            logging.error("STREAM ERROR:" + str(e))
            stream = None


