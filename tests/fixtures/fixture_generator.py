"""
This script pulled the 2011 election results webpage on Nov. 3, 2026.
(full url below in the script)
All <script> tags from the page HTML were extracted and used to create
test fixtures. The default collection of tags was verified to contain
only a single instance of a match for the regex expression used by the
function to be tested. Further test fixtures were generated via copying
and careful manual manipulation of the default tag collection. A total of
six fixtures were created to cover the following scenarios:

1. one_digest.html  ->  a single match for the regex pattern in a single
tag
    Expected Return: A single digest

2. zero_digests.html  ->  no matches for the regex pattern in any tag
    Expected Return: Exception raised with count = 0

3. duplicated_digest_same_tag.html  ->  a match for the regex pattern
duplicated within the same tag
    Expected Return: A single digest that matches scenario 1

4. duplicated_digest_different_tags.html  ->  a match for the regex
pattern duplicated in a different tag
    Expected Return: A single digest that matches scenario 1

5. two_digests_same_tag.html  ->  a match for the regex pattern  within
the same tag with a single hex character modified in the digest
    Expected Return: Exception raised with count = 2

6. two_digests_different_tags.html  ->  a match for the regex pattern in
a different tag with a single hex character modified in the digest
    Expected Return: Exception raised with count = 2

Note: The collection of script tags contains a second digest that is
intentionally ignored. Only the digest contained in the regex pattern
specified by csom_file_finder.py is of interest. 
"""
import sys
from pathlib import Path

import bs4
import requests

from scripts.environment.config import TIMEOUT


def main() -> None:
    url = 'https://elect.ky.gov/results/2010-2019/Pages/2011primaryandgeneralelectionresults.aspx'
    header_dict = {'User-Agent':'ky-elections-etl/0.1 (pjslouisville502@gmail.com)'}
    response = requests.get(url=url, headers=header_dict, timeout=TIMEOUT)
    if response.status_code != 200:
        sys.exit(f"GET response status code: {response.status_code}")
    parsed_html = bs4.BeautifulSoup(response.text, 'html.parser')
    script_tags = parsed_html.find_all('script')
    contents = "\n".join(map(str, script_tags))
    path = Path('tests/fixtures/one_digest.html')
    path.write_text(contents)

if __name__ == "__main__":
    main()