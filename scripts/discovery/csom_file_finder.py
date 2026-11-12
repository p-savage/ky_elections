import re
import sys
import time

import requests
from bs4 import BeautifulSoup

from scripts.environment.config import (
    MAX_TRIES,
    RETRY_STATUS_CODES,
    SLEEP_TIME,
    TIMEOUT,
)


class DigestExtractionError(Exception):
    def __init__(self, count: int) -> None:
        self.count = count
        super().__init__(f"{self.count} distinct digests found.")

class PostRequestError(Exception):
    def __init__(
            self,
            exception: Exception | None,
            status_code: int | None,
            message: str,
        ) -> None:
        self.exception = exception
        self.status_code = status_code
        self.message = message
        super().__init__(f"{self.message}")

ELECTION_YEAR = 2011
URL_STEM = 'https://elect.ky.gov'
ROW_LIMIT = 30
FIRST_URL = (
    'https://elect.ky.gov/results/2010-2019/Pages/'
    '2011primaryandgeneralelectionresults.aspx'
)
FIRST_HEADER = {
    'User-Agent':'ky-elections-etl/0.1 (pjslouisville502@gmail.com)'
}
SECOND_URL = (
    'https://elect.ky.gov/results/2010-2019/_vti_bin/client.svc/ProcessQuery'
)
SECOND_HEADER = {
    'User-Agent':'ky-elections-etl/0.1 (pjslouisville502@gmail.com)',
    'Content-Type':'text/xml',
    'X-Requested-With':'XMLHttpRequest',
}
KY_COUNTY_COUNT = 120
FATAL_REQUEST_EXCEPTIONS = ( #MUST BE FIRST EXCEPT CLAUSE
    requests.exceptions.SSLError, #subclass of ConnectionError
    requests.exceptions.ProxyError, #subclass of ConnecttionError
    requests.exceptions.TooManyRedirects,
    requests.exceptions.MissingSchema,
    requests.exceptions.InvalidSchema,
    requests.exceptions.InvalidURL,
    requests.exceptions.ContentDecodingError,
) 
TRANSIENT_REQUEST_EXCEPTIONS = (
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.ConnectionError,
)

def get_results_page(
        session: requests.Session,
        election_year: int,
) -> str:

    for _ in range(MAX_TRIES):
        try:
            response = session.get(
                url=FIRST_URL,
                headers=FIRST_HEADER,
                timeout=TIMEOUT,
            )
        except FATAL_REQUEST_EXCEPTIONS as fatal:
            sys.exit(f"{type(fatal).__name__} for {election_year} page.")
        except TRANSIENT_REQUEST_EXCEPTIONS:
            time.sleep(SLEEP_TIME)
            continue
        except requests.exceptions.RequestException as catch_all:
            sys.exit(
                f"{type(catch_all).__name__} for "
                f"{election_year} page.")
        if response.status_code == 200:
            break
        elif response.status_code in RETRY_STATUS_CODES:
            time.sleep(SLEEP_TIME)
            continue
        else:
            sys.exit(
                f"YEAR: {election_year} "
                f"STATUS CODE: {response.status_code}"
            )
    else:
        sys.exit(f"Max tries exceeded for {election_year} page.")
    return response.text

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

def extract_county_list(html_str: str) -> list[str]:

    html = BeautifulSoup(html_str,'html.parser')
    general_dd_list = html.find_all('select', id='ddCountyGeneral')
    if len(general_dd_list) != 1:
        sys.exit("MULTIPLE GENERAL TAGS FOUND")
    primary_dd_list = html.find_all('select', id='ddCountyPrimary')
    if len(primary_dd_list) != 1:
        sys.exit("MULTIPLE PRIMARY TAGS FOUND")
    general_option_tags = general_dd_list[0].find_all('option')
    primary_option_tags = primary_dd_list[0].find_all('option')
    if (general_option_tags == primary_option_tags
        and len(general_option_tags) == KY_COUNTY_COUNT):
        counties = []
        for tag in general_option_tags:
            counties.append(tag.text)
    else:
        sys.exit(
            "UNEXPECTED DD MENU OPTIONS SHAPE\n"
            f"Expected county count: {KY_COUNTY_COUNT}\n"
            f"No. of General Options: {len(general_option_tags)}\n"
            f"No. of Primary Options: {len(primary_option_tags)}"
        )
    return counties

def form_request_body(
        election_year: int,
        election_type: str,
        folder: str,
        row_limit: int,
) -> str:
    if 2010 <= election_year <= 2019:
        decade = '2010-2019'
    else:
        decade = '2020-2029'
    server_relative_path = (
        f'/results/{decade}/{election_year}ElectionReports/'
        f'{election_type}/{folder.upper()}'
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
    '&lt;View Scope="Recursive"&gt;&lt;Query&gt;&lt;Where&gt;'
    '&lt;Eq&gt;&lt;FieldRef Name="FileDirRef" /&gt;'
    '&lt;Value Type="Text"&gt;'f'{server_relative_path}''&lt;/Value&gt;'
    '&lt;/Eq&gt;&lt;/Where&gt;'
    '&lt;OrderBy&gt;&lt;FieldRef Name="FileDirRef" Ascending="True" /&gt;'
    '&lt;FieldRef Name="FileLeafRef" Ascending="False" /&gt;&lt;/OrderBy&gt;'
    '&lt;/Query&gt;&lt;RowLimit&gt;'f'{row_limit}''&lt;/RowLimit&gt;'
    '&lt;/View&gt;'
    '</Property></Parameter></Parameters>'
    '</Method></ObjectPaths></Request>')
    return body

def post_process_query(
        session: requests.Session,
        complete_header: dict[str,str],
        data: str,
        timeout: float,
) -> list:

    for _ in range(MAX_TRIES):
        try:
            post_response = session.post(
                url=SECOND_URL,
                headers=complete_header,
                data=data,
                timeout=timeout,
            )
        except FATAL_REQUEST_EXCEPTIONS as fatal:
            raise PostRequestError(
                exception=fatal,
                status_code=None,
                message=f"{type(fatal).__name__}"
            )    
        except TRANSIENT_REQUEST_EXCEPTIONS:
            time.sleep(SLEEP_TIME)
            continue
        except requests.exceptions.RequestException as catch_all:
            raise PostRequestError(
                exception=catch_all,
                status_code=None,
                message=f"{type(catch_all).__name__}"
            )
        if post_response.status_code == 200:
            break
        elif post_response.status_code in RETRY_STATUS_CODES:
            time.sleep(SLEEP_TIME)
            continue
        else:
            raise PostRequestError(
                exception=None,
                status_code=post_response.status_code,
                message="Fatal status code",
            )
    else:
        raise PostRequestError(
            exception=None,
            status_code=None,
            message="Max retries exceeded."
        )
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
    html_str = get_results_page(session=session, election_year=ELECTION_YEAR)
    try:
        digest = extract_digest(html_str=html_str)
    except DigestExtractionError as e:
        sys.exit(str(e))
    counties = extract_county_list(html_str=html_str)
    complete_second_header = SECOND_HEADER | {'X-RequestDigest' : digest}
    election_types = ['General', 'Primary',]
    request_queue = counties.copy()
    request_queue.append('Statewide')
    row_limit = ROW_LIMIT
    for folder in request_queue:
        for election_type in election_types:
            data = form_request_body(
                election_year = ELECTION_YEAR,
                election_type = election_type,
                folder = folder,
                row_limit = row_limit,
            )
            try:
                parsed_json = post_process_query(
                    session=session,
                    complete_header=complete_second_header,
                    data=data,
                    timeout=TIMEOUT,
                )
            except PostRequestError as post_error:
                print(
                    f"{folder}/{election_type}:\n"
                    f"{post_error.exception}\n"
                    f"{post_error.status_code}\n"
                    f"{post_error.message}"
                    )
                time.sleep(SLEEP_TIME)
                continue
            zip_urls = compile_zip_urls(
                parsed_json=parsed_json,
                row_limit=row_limit,
            )
            for url in zip_urls:
                print(url)
            time.sleep(SLEEP_TIME)

if __name__ == "__main__":
    main()