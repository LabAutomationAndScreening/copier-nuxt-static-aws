import hashlib
import json
import logging
import mimetypes
import os
from collections.abc import Sequence
from pathlib import Path

import pulumi
from ephemeral_pulumi_deploy import append_resource_suffix
from ephemeral_pulumi_deploy import common_tags
from ephemeral_pulumi_deploy import common_tags_native
from ephemeral_pulumi_deploy import get_aws_account_id
from ephemeral_pulumi_deploy import get_config_str
from ephemeral_pulumi_deploy.utils import PROTECTED_ENVS
from pulumi import Output
from pulumi import Resource
from pulumi import ResourceOptions
from pulumi import export
from pulumi_aws.acm import Certificate
from pulumi_aws.acm.outputs import CertificateDomainValidationOption
from pulumi_aws.cloudfront import Function
from pulumi_aws.iam import GetPolicyDocumentStatementArgs
from pulumi_aws.iam import GetPolicyDocumentStatementPrincipalArgs
from pulumi_aws.iam import get_policy_document
from pulumi_aws.s3 import BucketObjectv2
from pulumi_aws_native import cloudfront
from pulumi_aws_native import s3
from pulumi_command.local import Command

from .jinja_constants import APP_DIRECTORY_NAME
from .jinja_constants import APP_DOMAIN_NAME
from .jinja_constants import ATTACH_ACM_CERT_TO_CLOUDFRONT
from .jinja_constants import REDIRECT_BARE_DOMAIN_TO_APP_DOMAIN

RAW_DOMAIN_NAME = APP_DOMAIN_NAME.removeprefix("www.")

# CloudFront Functions (cloudfront-js-2.0) run in a restricted JavaScript runtime at the edge for every viewer request,
# so this stays dependency-free. BARE_DOMAIN and APP_DOMAIN are prepended as variable declarations when it is deployed.
# rawQueryString() is the query string exactly as the viewer sent it (undefined when the URL has no `?`); the parsed
# request.querystring object would lose the parameters' order.
# TODO: once this template has an E2E harness that runs against a deployed stack, cover the redirect there:
#   - https://<bare>/path?b=2&a=1 answers 301 with Location https://<app>/path?b=2&a=1 (path and parameter order kept)
#   - a URL ending in a bare `?`, and one with no query string at all
#   - a request for the app domain passes through and is served (200)
#   - http://<bare> ends at https://<app>
BARE_DOMAIN_REDIRECT_FUNCTION_BODY = """
function handler(event) {
    var request = event.request;
    if (request.headers.host.value !== BARE_DOMAIN) {
        return request;
    }
    var querystring = request.rawQueryString();
    return {
        statusCode: 301,
        statusDescription: "Moved Permanently",
        headers: {
            location: { value: "https://" + APP_DOMAIN + request.uri + (querystring === undefined ? "" : "?" + querystring) },
        },
    };
}
"""

logger = logging.getLogger(__name__)

repo_root = Path(__file__).parent.parent.parent.parent


def _get_mime_type(file_path: Path) -> str:
    content_type, _ = mimetypes.guess_type(file_path)
    if content_type is None:
        return "application/octet-stream"
    return content_type


def _compute_directory_hash(base_dir: Path) -> str:
    """Compute a hash of all files in a directory based on their paths and content."""
    hash_md5 = hashlib.md5()  # noqa: S324 # we don't care about security here, just if files have changed for creating the invalidation

    for dirpath, _, filenames in sorted(os.walk(base_dir)):
        for filename in sorted(filenames):
            file_path = Path(dirpath) / filename
            rel_path = os.path.relpath(file_path, base_dir)

            # Hash the relative path
            hash_md5.update(rel_path.encode())

            with file_path.open("rb") as f:
                hash_md5.update(f.read())

    return hash_md5.hexdigest()


def _upload_assets_to_s3(*, bucket_id: Output[str], base_dir: Path) -> list[Resource]:
    uploads: list[Resource] = []
    for dirpath, _, filenames in os.walk(base_dir):
        for filename in filenames:
            file_path = Path(dirpath) / filename

            # Compute the S3 key relative to the base directory.
            # For example, if base_dir is "./upload-dir" and file_path is "./upload-dir/docs/readme.txt",
            # then s3_key will be "docs/readme.txt".
            s3_key = os.path.relpath(file_path, base_dir)
            # Since resource names cannot have slashes, we replace them with dashes.
            resource_name = append_resource_suffix(s3_key.replace(os.sep, "-"), max_length=200)
            uploads.append(
                BucketObjectv2(
                    resource_name,
                    content_type=_get_mime_type(file_path),
                    bucket=bucket_id,
                    key=s3_key,
                    source=pulumi.FileAsset(str(file_path)),
                    source_hash=hashlib.md5(file_path.read_bytes()).hexdigest(),  # noqa: S324 # we're just using this for change detection, not security
                    tags=common_tags(),
                )
            )
    return uploads


def pulumi_program() -> None:
    """Execute creating the stack."""
    aws_account_id = get_aws_account_id()
    export("aws-account-id", aws_account_id)
    env = get_config_str("proj:env")

    export("env", env)

    # Create Resources Here
    bucket_name = APP_DOMAIN_NAME if env == "prod" else f"{pulumi.get_stack()}.{APP_DOMAIN_NAME}"
    app_website_bucket = s3.Bucket(
        bucket_name,
        bucket_name=bucket_name,
        website_configuration=s3.BucketWebsiteConfigurationArgs(index_document="index.html", error_document="404.html"),
        tags=common_tags_native(),
        public_access_block_configuration=s3.BucketPublicAccessBlockConfigurationArgs(
            block_public_acls=False, block_public_policy=False, ignore_public_acls=False, restrict_public_buckets=False
        ),
    )
    export("app-bucket-website-url", app_website_bucket.website_url)
    policy_json = app_website_bucket.bucket_name.apply(
        lambda name: (
            get_policy_document(
                statements=[
                    GetPolicyDocumentStatementArgs(
                        effect="Allow",
                        principals=[
                            GetPolicyDocumentStatementPrincipalArgs(
                                type="*",
                                identifiers=["*"],
                            )
                        ],
                        actions=["s3:GetObject"],
                        resources=[f"arn:aws:s3:::{name}/*"],
                    ),
                ]
            ).json
        )
    )
    _ = s3.BucketPolicy(
        append_resource_suffix("app-website"),
        bucket=app_website_bucket.bucket_name,
        policy_document=policy_json,
    )
    static_files_dir = repo_root / APP_DIRECTORY_NAME / ".output" / "public"

    all_uploads = _upload_assets_to_s3(bucket_id=app_website_bucket.id, base_dir=static_files_dir)
    if env in PROTECTED_ENVS:
        # Changing the certificate's names replaces it, which CloudFront rejects while the new certificate is still pending
        # validation. So toggle REDIRECT_BARE_DOMAIN_TO_APP_DOMAIN only in a deploy where ATTACH_ACM_CERT_TO_CLOUDFRONT is
        # False, and re-attach in a later deploy once the new certificate is ISSUED.
        subject_alternative_names: list[str] | None = (
            None  # None rather than [] so stacks without the redirect see no diff
        )
        if REDIRECT_BARE_DOMAIN_TO_APP_DOMAIN:
            subject_alternative_names = [RAW_DOMAIN_NAME]
        certificate = Certificate(
            append_resource_suffix("certificate"),
            domain_name=f"*.{RAW_DOMAIN_NAME}",
            subject_alternative_names=subject_alternative_names,
            validation_method="DNS",
            region="us-east-1",  # ACM certificates for CloudFront must be in us-east-1 (see: https://docs.aws.amazon.com/acm/latest/userguide/acm-services.html#acm-cloudfront)
            tags=common_tags(),
        )
        origin_id = "S3OriginMyBucket"
        origin_domain = app_website_bucket.website_url.apply(lambda full_url: full_url.removeprefix("http://"))
        viewer_certificate = cloudfront.DistributionViewerCertificateArgs(cloud_front_default_certificate=True)
        aliases: list[str] = []
        function_associations: list[cloudfront.DistributionFunctionAssociationArgs] | None = (
            None  # None rather than [] so stacks without the redirect see no diff
        )
        bare_domain_redirect: Function | None = None
        if REDIRECT_BARE_DOMAIN_TO_APP_DOMAIN:
            bare_domain_redirect = Function(
                append_resource_suffix("bare-domain-redirect"),
                name=append_resource_suffix("bare-domain-redirect"),
                runtime="cloudfront-js-2.0",
                comment=f"Redirects {RAW_DOMAIN_NAME} to https://{APP_DOMAIN_NAME}",
                code=f"var BARE_DOMAIN = {json.dumps(RAW_DOMAIN_NAME)};\nvar APP_DOMAIN = {json.dumps(APP_DOMAIN_NAME)};\n{BARE_DOMAIN_REDIRECT_FUNCTION_BODY}",
                publish=True,
            )
        if ATTACH_ACM_CERT_TO_CLOUDFRONT:
            aliases.append(APP_DOMAIN_NAME)
            if bare_domain_redirect is not None:
                aliases.append(RAW_DOMAIN_NAME)
                function_associations = [
                    cloudfront.DistributionFunctionAssociationArgs(
                        event_type="viewer-request", function_arn=bare_domain_redirect.arn
                    )
                ]
            viewer_certificate = cloudfront.DistributionViewerCertificateArgs(  # TODO: determine if this needs to be attached to EVERY distribution, or just a single distribution unrelated to the actual bucket
                acm_certificate_arn=certificate.arn,
                ssl_support_method="sni-only",
                minimum_protocol_version="TLSv1.2_2021",
            )
        app_cloudfront = cloudfront.Distribution(
            append_resource_suffix("app"),
            distribution_config=cloudfront.DistributionConfigArgs(
                aliases=aliases,
                price_class="PriceClass_100",
                comment=f"{RAW_DOMAIN_NAME} App CloudFront Distribution",
                origins=[
                    cloudfront.DistributionOriginArgs(
                        domain_name=origin_domain,
                        id=origin_id,
                        custom_origin_config=cloudfront.DistributionCustomOriginConfigArgs(
                            http_port=80,
                            https_port=443,
                            origin_protocol_policy="http-only",
                            origin_ssl_protocols=["TLSv1.2"],
                        ),
                    )
                ],
                default_cache_behavior=cloudfront.DistributionDefaultCacheBehaviorArgs(
                    target_origin_id=origin_id,
                    viewer_protocol_policy="redirect-to-https",
                    allowed_methods=["GET", "HEAD"],
                    cached_methods=["GET", "HEAD"],
                    function_associations=function_associations,
                    forwarded_values=cloudfront.DistributionForwardedValuesArgs(
                        query_string=False, cookies=cloudfront.DistributionCookiesArgs(forward="none")
                    ),
                ),
                enabled=True,
                ipv6_enabled=True,
                default_root_object="index.html",
                restrictions=cloudfront.DistributionRestrictionsArgs(
                    geo_restriction=cloudfront.DistributionGeoRestrictionArgs(restriction_type="none")
                ),
                viewer_certificate=viewer_certificate,
            ),
            tags=common_tags_native(),
        )

        export("app-cloudfront-domain-name", app_cloudfront.domain_name)
        _ = Command(
            append_resource_suffix("app-cloudfront-invalidation"),
            create=app_cloudfront.id.apply(
                lambda distribution_id: (
                    f'aws cloudfront create-invalidation --distribution-id {distribution_id} --paths "/*" && echo {_compute_directory_hash(static_files_dir)}'
                )
            ),
            opts=ResourceOptions(depends_on=all_uploads),
        )

        def _extract_host(options: Sequence[CertificateDomainValidationOption]) -> str:
            record_name = options[0].resource_record_name
            assert record_name is not None
            return record_name.removesuffix(f".{RAW_DOMAIN_NAME}.")

        cname_host = certificate.domain_validation_options.apply(_extract_host)
        export("certificate-cname-host", cname_host)
        export("certificate-cname-value", certificate.domain_validation_options[0].resource_record_value)
