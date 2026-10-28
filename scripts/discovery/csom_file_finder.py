import requests

from scripts.environment import config

url = 'https://elect.ky.gov/results/2010-2019/Pages/2011primaryandgeneralelectionresults.aspx'

headers = config.HEADER

response = requests.get(url=url, headers=headers)

print(response.text)

# locate and extract the digest from the initial site load
# use that digest in the subsequent request headers along with content_type and X-Requested-With
# reconstruct the request body 