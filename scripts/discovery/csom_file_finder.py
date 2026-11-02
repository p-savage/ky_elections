import json
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

first_url = 'https://elect.ky.gov/results/2010-2019/Pages/2011primaryandgeneralelectionresults.aspx'
first_header = {'User-Agent':'ky-elections-etl/0.1 (pjslouisville502@gmail.com)'}
second_url = 'https://elect.ky.gov/results/2010-2019/_vti_bin/client.svc/ProcessQuery'
second_header = {
    'User-Agent':'ky-elections-etl/0.1 (pjslouisville502@gmail.com)',
    'Content-Type':'text/xml',
    'X-Requested-With':'XMLHttpRequest',
}
data = '<Request xmlns="http://schemas.microsoft.com/sharepoint/clientquery/2009" SchemaVersion="15.0.0.0" LibraryVersion="16.0.0.0" ApplicationName="Javascript Library"><Actions><ObjectPath Id="1" ObjectPathId="0" /><ObjectPath Id="3" ObjectPathId="2" /><ObjectPath Id="5" ObjectPathId="4" /><ObjectPath Id="7" ObjectPathId="6" /><ObjectIdentityQuery Id="8" ObjectPathId="6" /><ObjectPath Id="10" ObjectPathId="9" /><Query Id="11" ObjectPathId="9"><Query SelectAllProperties="false"><Properties /></Query><ChildItemQuery SelectAllProperties="false"><Properties><Property Name="FileLeafRef" SelectAll="true" /><Property Name="FileDirRef" SelectAll="true" /><Property Name="FileSizeDisplay" SelectAll="true" /></Properties></ChildItemQuery></Query></Actions><ObjectPaths><StaticProperty Id="0" TypeId="{3747adcd-a3c3-41b9-bfab-4a64dd2f1e0a}" Name="Current" /><Property Id="2" ParentId="0" Name="Web" /><Property Id="4" ParentId="2" Name="Lists" /><Method Id="6" ParentId="4" Name="GetByTitle"><Parameters><Parameter Type="String">2011ElectionReports</Parameter></Parameters></Method><Method Id="9" ParentId="6" Name="GetItems"><Parameters><Parameter TypeId="{3d248d7b-fc86-40a3-aa97-02a75d69fb8a}"><Property Name="AllowIncrementalResults" Type="Boolean">false</Property><Property Name="DatesInUtc" Type="Boolean">true</Property><Property Name="FolderServerRelativePath" Type="Null" /><Property Name="FolderServerRelativeUrl" Type="Null" /><Property Name="ListItemCollectionPosition" Type="Null" /><Property Name="ViewXml" Type="String">&lt;View Scope="Recursive"&gt;&lt;Query&gt;&lt;Where&gt;&lt;Or&gt;&lt;Contains&gt;&lt;FieldRef Name="FileDirRef" /&gt;&lt;Value Type="Text"&gt;General/Statewide&lt;/Value&gt;&lt;/Contains&gt;&lt;Contains&gt;&lt;FieldRef Name="FileDirRef" /&gt;&lt;Value Type="Text"&gt;General/Adair&lt;/Value&gt;&lt;/Contains&gt;&lt;/Or&gt;&lt;/Where&gt;&lt;OrderBy&gt;&lt;FieldRef Name="FileDirRef" Ascending="True" /&gt;&lt;FieldRef Name="FileLeafRef" Ascending="False" /&gt;&lt;/OrderBy&gt;&lt;/Query&gt;&lt;RowLimit&gt;30&lt;/RowLimit&gt;&lt;/View&gt;</Property></Parameter></Parameters></Method></ObjectPaths></Request>'

def main() -> None:

    s = requests.Session()
    response = s.get(url=first_url, headers=first_header, timeout=TIMEOUT)
    html_str = response.text
    try:
        digest = extract_digest(html_str=html_str)
    except DigestExtractionError as e:
        sys.exit(str(e))
    complete_second_header = second_header | {'X-RequestDigest' : digest}
    response = s.post(url=second_url,headers=complete_second_header,data=data,timeout=TIMEOUT)
    if response.status_code == 200:
        parsed = response.json()
        formatted = json.dumps(parsed,indent=4)
        print(formatted)
    else:
        print(response.status_code)

if __name__ == "__main__":
    main()