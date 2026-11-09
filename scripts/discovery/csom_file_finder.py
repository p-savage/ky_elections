import re
import sys

import requests
from bs4 import BeautifulSoup

from scripts.environment.config import TIMEOUT


class DigestExtractionError(Exception):
    def __init__(self, count: int) -> None:
        self.count = count
        super().__init__(f"{self.count} distinct digests found.")
        
def extract_digest(html_str: str) -> str:

    html = BeautifulSoup(html_str, 'html.parser')
    pattern = re.compile(r"formDigestElement\.value = '([^']+)'")
    script_tags = html.find_all('script')
    digests = set()
    for tag in script_tags:
        match_iterator = pattern.finditer(tag.text)
        for match in match_iterator:
            digests.add(match.group(1))
    if len(digests) == 1:
        return next(iter(digests))
    else:
        raise DigestExtractionError(count=len(digests))

URL_STEM = 'https://elect.ky.gov'
first_url = (
    'https://elect.ky.gov/results/2010-2019/Pages/'
    '2011primaryandgeneralelectionresults.aspx'
)
first_header = {
    'User-Agent':'ky-elections-etl/0.1 (pjslouisville502@gmail.com)'
}
second_url = (
    'https://elect.ky.gov/results/2010-2019/_vti_bin/client.svc/ProcessQuery'
)
second_header = {
    'User-Agent':'ky-elections-etl/0.1 (pjslouisville502@gmail.com)',
    'Content-Type':'text/xml',
    'X-Requested-With':'XMLHttpRequest',
}
def form_request_body(
        election_year: int,
        election_type: str,
        county: str,
        row_limit: int,
) -> str:
    if 2010 <= election_year <= 2019:
        decade = '2010-2019'
    else:
        decade = '2020-2029'
    server_relative_path = (
        f'/results/{decade}/{election_year}ElectionReports/'
        f'{election_type}/{county.upper()}'
        )
    body = ('<Request '
    'xmlns="http://schemas.microsoft.com/sharepoint/clientquery/2009" '
    'SchemaVersion="15.0.0.0" LibraryVersion="16.0.0.0" '
    'ApplicationName="Javascript Library">'
    '<Actions>'
    '<ObjectPath Id="1" ObjectPathId="0" />'
    '<ObjectPath Id="3" ObjectPathId="2" />'
    '<ObjectPath Id="5" ObjectPathId="4" />'
    '<ObjectPath Id="7" ObjectPathId="6" />'
    '<ObjectIdentityQuery Id="8" ObjectPathId="6" />'
    '<ObjectPath Id="10" ObjectPathId="9" />'
    '<Query Id="11" ObjectPathId="9">'
    '<Query SelectAllProperties="false"><Properties /></Query>'
    '<ChildItemQuery SelectAllProperties="false"><Properties>'
    '<Property Name="FileLeafRef" SelectAll="true" />'
    '<Property Name="FileDirRef" SelectAll="true" />'
    '<Property Name="FileSizeDisplay" SelectAll="true" />'
    '</Properties></ChildItemQuery></Query></Actions>'
    '<ObjectPaths>'
    '<StaticProperty Id="0" '
    'TypeId="{3747adcd-a3c3-41b9-bfab-4a64dd2f1e0a}" Name="Current" />'
    '<Property Id="2" ParentId="0" Name="Web" />'
    '<Property Id="4" ParentId="2" Name="Lists" />'
    '<Method Id="6" ParentId="4" Name="GetByTitle"><Parameters>'
    '<Parameter Type="String">'
    f'{election_year}''ElectionReports</Parameter></Parameters></Method>'
    '<Method Id="9" ParentId="6" Name="GetItems"><Parameters>'
    '<Parameter TypeId="{3d248d7b-fc86-40a3-aa97-02a75d69fb8a}">'
    '<Property Name="AllowIncrementalResults" Type="Boolean">false'
    '</Property>'
    '<Property Name="DatesInUtc" Type="Boolean">true</Property>'
    '<Property Name="FolderServerRelativePath" Type="Null" />'
    '<Property Name="FolderServerRelativeUrl" Type="Null" />'
    '<Property Name="ListItemCollectionPosition" Type="Null" />'
    '<Property Name="ViewXml" Type="String">'
    '&lt;View Scope="Recursive"&gt;&lt;Query&gt;&lt;Where&gt;&lt;Or'
    '&gt;&lt;Contains&gt;&lt;FieldRef Name="FileDirRef" /&gt;&lt;'
    'Value Type="Text"&gt;'f'{election_type}''/Statewide&lt;/Value'
    '&gt;&lt;/Contains&gt;&lt;Eq&gt;&lt;FieldRef Name="FileDirRef"'
    ' /&gt;&lt;Value Type="Text"&gt;'f'{server_relative_path}''&lt;/'
    'Value&gt;&lt;/Eq&gt;&lt;/Or&gt;&lt;/Where&gt;&lt;OrderBy'
    '&gt;&lt;FieldRef Name="FileDirRef" Ascending="True" /&gt;&lt;'
    'FieldRef Name="FileLeafRef" Ascending="False" /&gt;&lt;/OrderBy'
    '&gt;&lt;/Query&gt;&lt;RowLimit&gt;'f'{row_limit}''&lt;/RowLimit'
    '&gt;&lt;/View&gt;'
    '</Property></Parameter></Parameters>'
    '</Method></ObjectPaths></Request>')
    return body

def retrieve_county_results(
        session: requests.Session,
        complete_header: dict[str,str],
        data: str,
        timeout: float,
):

    post_response = session.post(
        url=second_url,
        headers=complete_header,
        data=data,
        timeout=timeout,
    )
    if post_response.status_code != 200:
        sys.exit(f"POST response status code: {post_response.status_code}")
    parsed_json = post_response.json()
    return parsed_json

def compile_zip_urls(parsed_json: list, row_limit: int) -> list[str]:
    zip_urls = []
    for element in parsed_json:
        if isinstance(element, dict) and "_Child_Items_" in element:
            list_items = element['_Child_Items_']
            if len(list_items) < row_limit:
                for dict_item in list_items:
                    zip_url = (URL_STEM+dict_item["FileDirRef"]
                               +"/"+dict_item["FileLeafRef"])
                    zip_urls.append(zip_url)
    return zip_urls

def main() -> None:

    session = requests.Session()
    get_response = session.get(
        url=first_url,
        headers=first_header,
        timeout=TIMEOUT,
    )
    if get_response.status_code != 200:
        sys.exit(f"GET response status code: {get_response.status_code}")
    html_str = get_response.text
    try:
        digest = extract_digest(html_str=html_str)
    except DigestExtractionError as e:
        sys.exit(str(e))
    complete_second_header = second_header | {'X-RequestDigest' : digest}
    election_year = 2011
    election_type = 'General'
    county = 'Caldwell'
    row_limit = 30
    data = form_request_body(
        election_year = election_year,
        election_type = election_type,
        county = county,
        row_limit = row_limit,
    )
    parsed_json = retrieve_county_results(
        session=session,
        complete_header=complete_second_header,
        data=data,
        timeout=TIMEOUT,
    )
    zip_urls = compile_zip_urls(
        parsed_json=parsed_json,
        row_limit=row_limit,
    )
    for url in zip_urls[:6]:
        print(url)

if __name__ == "__main__":
    main()