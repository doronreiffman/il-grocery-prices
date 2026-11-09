"""Pin what the public site's stack exposes (site-template.yaml; docs/headline-basket.md, "What a visitor sees"):
the built pages and day files through CloudFront, nothing else.

cfn-lint (run in CI) checks the template is valid CloudFormation; it cannot know that the bucket must stay
private or that only this distribution may read it, so those settings are asserted here. The template is read
with cfn-lint's decoder, as `tests/test_template.py` reads the collector's.
"""
from datetime import date
from pathlib import Path

import pytest
from cfnlint.decode import decode

from basket.site import FIXED_PAGES, day_key
from shopper.build import LEDGER
from shopper.freeze import scores_site_key, site_key
from shopper.product import page_path
from shopper.search import browse_path, pieces
from shopper.siteday import site_day_path

TEMPLATE = Path(__file__).parent.parent / "site-template.yaml"
CACHING_OPTIMIZED = "658327ea-f89d-4fab-a63d-7e88639e58f6"  # aws cloudfront list-cache-policies --type managed
SECURITY_HEADERS = "67f7725c-6f97-4210-82d7-5512b31e9d03"  # aws cloudfront list-response-headers-policies --type managed


@pytest.fixture(scope="module")
def template():
    body, matches = decode(str(TEMPLATE))
    assert not matches, matches
    return body


@pytest.fixture(scope="module")
def resources(template):
    return template["Resources"]


def walk(node):
    yield node
    if isinstance(node, dict):
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


def test_only_the_four_expected_resources(resources):
    assert {k: v["Type"] for k, v in resources.items()} == {
        "SiteBucket": "AWS::S3::Bucket",
        "SiteOriginAccessControl": "AWS::CloudFront::OriginAccessControl",
        "SiteDistribution": "AWS::CloudFront::Distribution",
        "SiteBucketPolicy": "AWS::S3::BucketPolicy",
    }


def test_the_bucket_is_private_and_owner_enforced(resources):
    props = resources["SiteBucket"]["Properties"]
    assert props["PublicAccessBlockConfiguration"] == {
        "BlockPublicAcls": True, "BlockPublicPolicy": True, "IgnorePublicAcls": True, "RestrictPublicBuckets": True}
    assert props["OwnershipControls"] == {"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]}
    rule = props["BucketEncryption"]["ServerSideEncryptionConfiguration"][0]
    assert rule["ServerSideEncryptionByDefault"] == {"SSEAlgorithm": "AES256"}


def test_the_bucket_keeps_every_version_of_a_published_file(resources):
    # A day file holds its revision reason and its earlier figures (B12): an upload that replaces it must leave
    # the published one recoverable.
    assert resources["SiteBucket"]["Properties"]["VersioningConfiguration"] == {"Status": "Enabled"}


def _rebuilt_prefixes() -> list[str]:
    """What a morning's build writes again under the same key: the product, browse and search folders, and the fixed
    pages, each named from the code's own keys."""
    folders = {key.split("/", 1)[0] + "/" for key in (page_path("2000000000046"), browse_path("\u05d0"), *pieces({}))}
    return sorted(folders | set(FIXED_PAGES))


def _record_keys() -> list[str]:
    """The files that are written once for a day (or only grow) and kept in every version."""
    day = date(2026, 11, 7)
    return [day_key(day), site_day_path(Path(), day).as_posix(), site_key(day), LEDGER, scores_site_key(day)]


def test_old_versions_of_rebuilt_pages_expire_after_30_days(resources):
    # The bucket keeps every version (B12's second guard), and a morning rebuilds every product, browse and search
    # file and the fixed pages: their older versions would pile up. Only a noncurrent version expires; the current
    # file never does, and nothing moves to another storage class.
    config = resources["SiteBucket"]["Properties"]["LifecycleConfiguration"]
    assert set(config) == {"Rules"}
    rules = config["Rules"]
    assert len(rules) == 8
    assert sorted(rule["Prefix"] for rule in rules) == _rebuilt_prefixes()
    assert len({rule["Id"] for rule in rules}) == 8
    for rule in rules:
        assert set(rule) == {"Id", "Status", "Prefix", "NoncurrentVersionExpiration"}, rule  # no ExpirationInDays, no transition
        assert rule["Status"] == "Enabled", rule
        assert rule["NoncurrentVersionExpiration"] == {"NoncurrentDays": 30}, rule


def test_no_lifecycle_prefix_matches_a_record_key(resources):
    # The day files, the forecasts and their ledger, and the scores are a record: every version of them stays (question H).
    assert _record_keys() == ["days/2026-11-07.json", "site-days/2026-11-07.json", "forecasts/2026-11-07.csv.gz",
                              "forecasts/ledger.csv", "scores/2026-11-07.csv.gz"]
    for rule in resources["SiteBucket"]["Properties"]["LifecycleConfiguration"]["Rules"]:
        assert not [key for key in _record_keys() if key.startswith(rule["Prefix"])], rule["Prefix"]


def test_no_principal_is_anyone(template):
    principals = [n["Principal"] for n in walk(template) if isinstance(n, dict) and "Principal" in n]
    assert principals, "the bucket policy should name a principal"
    assert all(p != "*" and p != {"AWS": "*"} for p in principals)


def test_the_policy_lets_only_this_distribution_read_objects(resources):
    props = resources["SiteBucketPolicy"]["Properties"]
    assert props["Bucket"] == {"Ref": "SiteBucket"}
    [statement] = props["PolicyDocument"]["Statement"]
    assert statement["Effect"] == "Allow"
    assert statement["Principal"] == {"Service": "cloudfront.amazonaws.com"}
    assert statement["Action"] == "s3:GetObject"
    assert statement["Resource"] == {"Fn::Sub": "${SiteBucket.Arn}/*"}
    assert statement["Condition"] == {"StringEquals": {
        "AWS:SourceArn": {"Fn::Sub": "arn:aws:cloudfront::${AWS::AccountId}:distribution/${SiteDistribution}"}}}


def test_cloudfront_signs_every_request_to_the_bucket(resources):
    config = resources["SiteOriginAccessControl"]["Properties"]["OriginAccessControlConfig"]
    assert config["OriginAccessControlOriginType"] == "s3"
    assert config["SigningBehavior"] == "always"
    assert config["SigningProtocol"] == "sigv4"


def test_the_origin_is_the_regional_bucket_through_the_access_control(resources):
    [origin] = resources["SiteDistribution"]["Properties"]["DistributionConfig"]["Origins"]
    # The global bucket.s3.amazonaws.com name returns 400 for buckets in Regions launched after 2019-03-20.
    assert origin["DomainName"] == {"Fn::GetAtt": ["SiteBucket", "RegionalDomainName"]}
    assert origin["S3OriginConfig"] == {"OriginAccessIdentity": ""}
    assert origin["OriginAccessControlId"] == {"Fn::GetAtt": ["SiteOriginAccessControl", "Id"]}


def test_viewers_get_https_read_only_cached_pages_with_security_headers(resources):
    config = resources["SiteDistribution"]["Properties"]["DistributionConfig"]
    assert config["Enabled"] is True
    assert config["DefaultRootObject"] == "index.html"
    assert config["PriceClass"] == "PriceClass_100"
    assert "Aliases" not in config and "Logging" not in config
    behavior = config["DefaultCacheBehavior"]
    assert behavior["ViewerProtocolPolicy"] == "redirect-to-https"
    assert behavior["AllowedMethods"] == ["GET", "HEAD"]
    assert behavior["CachePolicyId"] == CACHING_OPTIMIZED
    assert behavior["ResponseHeadersPolicyId"] == SECURITY_HEADERS
    assert behavior["Compress"] is True
    assert behavior["TargetOriginId"] == config["Origins"][0]["Id"]


def test_outputs_name_what_publish_sh_and_sync_sh_read(template):
    assert set(template["Outputs"]) == {"SiteBucketName", "SiteDistributionId", "SiteDomainName"}
    assert template["Outputs"]["SiteBucketName"]["Value"] == {"Ref": "SiteBucket"}
    assert template["Outputs"]["SiteDistributionId"]["Value"] == {"Ref": "SiteDistribution"}
    assert template["Outputs"]["SiteDomainName"]["Value"] == {"Fn::GetAtt": ["SiteDistribution", "DomainName"]}
