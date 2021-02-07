import os
import logging
import requests
import json
from aiogram import Bot, types
import asyncio

class Twits:

    def __init__(self):
        bearer_token = os.environ["TWITTER_ACCESS_TOKEN"]
        self.headers = {"Authorization": "Bearer {}".format(bearer_token)}
        self.twitter_search_url = "https://api.twitter.com/2/tweets/search/recent?query={}&{}"
        self.twitter_stream_url = "https://api.twitter.com/2/tweets/search/stream"
        self.chat_ids = [1442973965]
        self.stream = None
    
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
            {"value": "dog from:5dog12", "tag": "doge 5dog12"},
            {"value": "cat from:5dog12", "tag": "btc 5dog12"},
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


