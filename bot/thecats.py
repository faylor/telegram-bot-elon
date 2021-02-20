import requests
import os
import urllib.parse

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

def search_pix(query):
    api_key = os.environ["PIXABAY"]
    q = urllib.parse.quote(query)
    url = "https://pixabay.com/api/?key=" + api_key + "&q=" + q
    contents = requests.get(url)
    js = contents.json()
    hits = js["hits"]
    if len(hits) > 0:
        first_hit = hits[0]
        print(first_hit)
        if "imageURL" in first_hit:
            url = first_hit["imageURL"]
        else:
            url = None
    else:
        url = None 
    return url
	
    