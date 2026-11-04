from pathlib import Path

import pytest

import scripts.discovery.csom_file_finder as csom_f_f

FIXTURE_DIR = Path(__file__).parent.parent/'fixtures'

digest = '0xD573377146FC7FD967A1ADFACF1D7013106C7AD6CDD70187AC70852A462D8027239EFBF9D438CA9DA45178128D245A547AE188825CEC986E4D4C84C77DECDFC5,03 Nov 2026 19:46:29 -0000'

@pytest.mark.parametrize(
    'file_path',
    [
        FIXTURE_DIR/'one_digest.html',
        FIXTURE_DIR/'duplicated_digest_same_tag.html',
        FIXTURE_DIR/'duplicated_digest_different_tags.html',
    ],                 
)
def test_extract_digest_success_branch(file_path):
    contents = file_path.read_text()
    assert csom_f_f.extract_digest(contents) == digest

@pytest.mark.parametrize(
    'file_path, count',
    [
        (FIXTURE_DIR/'zero_digests.html', 0),
        (FIXTURE_DIR/'two_digests_same_tag.html', 2),
        (FIXTURE_DIR/'two_digests_different_tags.html', 2),
    ],
)
def test_extract_digest_failure_branch(file_path, count):
    contents = file_path.read_text()
    with pytest.raises(csom_f_f.DigestExtractionError) as e:
        csom_f_f.extract_digest(contents)
    assert e.value.count == count