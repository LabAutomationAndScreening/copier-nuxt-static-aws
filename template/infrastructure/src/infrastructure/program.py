import logging
import mimetypes
import os
from pathlib import Path
import logging
import mimetypes
import os
from pathlib import Path
from uuid import uuid4

import pulumi
from ephemeral_pulumi_deploy import append_resource_suffix
from ephemeral_pulumi_deploy import common_tags_native
from ephemeral_pulumi_deploy import get_aws_account_id
from ephemeral_pulumi_deploy import get_config_str
from ephemeral_pulumi_deploy.utils import PROTECTED_ENVS
from pulumi import Output
from pulumi import Resource
from pulumi import ResourceOptions
from pulumi import export
from pulumi_aws.iam import GetPolicyDocumentStatementArgs
from pulumi_aws.iam import GetPolicyDocumentStatementPrincipalArgs
from pulumi_aws.iam import get_policy_document
from pulumi_aws.s3 import BucketObjectv2
from pulumi_aws_native import cloudfront
from pulumi_aws_native import s3
from pulumi_command.local import Command
import pulumi
from ephemeral_pulumi_deploy import append_resource_suffix
from ephemeral_pulumi_deploy import common_tags_native
from ephemeral_pulumi_deploy import get_aws_account_id
from ephemeral_pulumi_deploy import get_config_str
from ephemeral_pulumi_deploy.utils import PROTECTED_ENVS
from pulumi import Output
from pulumi import export
from pulumi_aws.iam import GetPolicyDocumentStatementArgs
from pulumi_aws.iam import GetPolicyDocumentStatementPrincipalArgs
from pulumi_aws.iam import get_policy_document
from pulumi_aws.s3 import BucketObjectv2
from pulumi_aws_native import cloudfront
from pulumi_aws_native import s3

from .jinja_constants import APP_DIRECTORY_NAME
from .jinja_constants import APP_DOMAIN_NAME

logger = logging.getLogger(__name__)

repo_root = Path(__file__).parent.parent.parent.parent


def _get_mime_type(file_path: Path) -> str:
    content_type, _ = mimetypes.guess_type(file_path)
    return content_type or "application/octet-stream"


def _upload_assets_to_s3(*, bucket_id: Output[str], base_dir: Path) -> None:
    for dirpath, _, filenames in os.walk(base_dir):
        for filename in filenames:
            file_path = Path(dirpath) / filename

            # Compute the S3 key relative to the base directory.
            # For example, if base_dir is "./upload-dir" and file_path is "./upload-dir/docs/readme.txt",
            # then s3_key will be "docs/readme.txt".
            s3_key = os.path.relpath(file_path, base_dir)
            # Since resource names cannot have slashes, we replace them with dashes.
            resource_name = append_resource_suffix(s3_key.replace(os.sep, "-"), max_length=200)
            _ = BucketObjectv2(
                resource_name,
                content_type=_get_mime_type(file_path),
                bucket=bucket_id,
                key=s3_key,
                source=pulumi.FileAsset(str(file_path)),
            )


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
        lambda name: get_policy_document(
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
    _ = s3.BucketPolicy(
        append_resource_suffix("app-website"),
        bucket=app_website_bucket.bucket_name,  # pyright: ignore[reportArgumentType] # it doesn't seem like it's possible for the bucket name to actually be Output[None]...not sure why the typing suggests that...and not sure a way to assert about Output subtypes
        policy_document=policy_json,
    )

    all_uploads = _upload_assets_to_s3(
        bucket_id=app_website_bucket.id, base_dir=repo_root / APP_DIRECTORY_NAME / ".output" / "public"
    )
    if env in PROTECTED_ENVS:
        origin_id = "S3OriginMyBucket"
        origin_domain = app_website_bucket.website_url.apply(lambda full_url: full_url.removeprefix("http://"))
        app_cloudfront = cloudfront.Distribution(
            append_resource_suffix("app"),
            distribution_config=cloudfront.DistributionConfigArgs(
                price_class="PriceClass_100",
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
                viewer_certificate=cloudfront.DistributionViewerCertificateArgs(cloud_front_default_certificate=True),
            ),
            tags=common_tags_native(),
        )

        export("app-cloudfront-domain-name", app_cloudfront.domain_name)
        _ = Command(
            append_resource_suffix("app-cloudfront-invalidation"),
            create=app_cloudfront.id.apply(
                lambda distribution_id: f'aws cloudfront create-invalidation --distribution-id {distribution_id} --paths "/*" && echo {uuid4()}'
            ),
            opts=ResourceOptions(depends_on=all_uploads),
        )
