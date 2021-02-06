import os
import requests
import json
from aiogram import Bot, types

class Twits:

    def __init__(self):
        bearer_token = os.environ["TWITTER_ACCESS_TOKEN"]
        self.headers = {"Authorization": "Bearer {}".format(bearer_token)}
        self.twitter_search_url = "https://api.twitter.com/2/tweets/search/recent?query={}&{}"
        self.twitter_stream_url = "https://api.twitter.com/2/tweets/search/stream"
    
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
            {"value": "doge from:elonmusk", "tag": "doge elon"},
            {"value": "bitcoin from:elonmusk", "tag": "btc elon"},
        ]
        payload = {"add": sample_rules}
        response = requests.post(self.twitter_stream_url + "/rules", headers=self.headers, json=payload)
        if response.status_code != 201:
            raise Exception(
                "Cannot add rules (HTTP {}): {}".format(response.status_code, response.text)
            )
        print(json.dumps(response.json()))


    def get_stream(self, bot: Bot, chat_id):
        response = requests.get(self.twitter_stream_url, headers=self.headers, stream=True)
        print(response.status_code)
        if response.status_code != 200:
            raise Exception(
                "Cannot get stream (HTTP {}): {}".format(
                    response.status_code, response.text
                )
            )
        for response_line in response.iter_lines():
            if response_line:
                json_response = json.loads(response_line)
                bot.send_message(chat_id=chat_id, text="Got A Tweet: " + str(json_response["data"]["text"]))
                print(json.dumps(json_response, indent=4, sort_keys=True))

