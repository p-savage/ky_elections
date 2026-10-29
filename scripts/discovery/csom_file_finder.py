import re

import requests
from bs4 import BeautifulSoup

from scripts.environment import config

url = 'https://elect.ky.gov/results/2010-2019/Pages/2011primaryandgeneralelectionresults.aspx'

headers = config.HEADER

response = requests.get(url=url, headers=headers)
html = BeautifulSoup(response.text, 'html.parser')
pattern = re.compile(r"formDigestElement\.value = '([^']+)'")
script_tags = html.find_all('script')
digests = []
for tag in script_tags:
    m = pattern.search(tag.text)
    if m is not None:
        digests.append(m.group(1))

if len(digests) == 1:
    print(digests[0])
elif len(digests) > 1:
    print(f"Number of matching digests: {len(digests)}")
else:
    print("No digests found.")


# use that digest in the subsequent request headers along with content_type and X-Requested-With
# reconstruct the request body