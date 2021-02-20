import requests

def getTheApiUrl(animal):
    contents = requests.get('https://api.the' + animal + 'api.com/v1/images/search')
    js = contents.json()
    print(js)
    url = js[0]["url"]
    return url

def get_a_fox():
    contents = requests.get("https://randomfox.ca/floof/?ref=apilist.fun")
    js = contents.json()
    url = js["image"]
    return url