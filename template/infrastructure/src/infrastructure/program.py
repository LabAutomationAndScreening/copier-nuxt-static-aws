import logging

import pulumi
from ephemeral_pulumi_deploy import append_resource_suffix
from ephemeral_pulumi_deploy import common_tags_native
from ephemeral_pulumi_deploy import get_aws_account_id
from ephemeral_pulumi_deploy import get_config_str
from pulumi import export
from pulumi_aws.iam import GetPolicyDocumentStatementArgs
from pulumi_aws.iam import GetPolicyDocumentStatementPrincipalArgs
from pulumi_aws.iam import get_policy_document
from pulumi_aws_native import cloudfront
from pulumi_aws_native import s3

logger = logging.getLogger(__name__)


def pulumi_program() -> None:
    """Execute creating the stack."""
    aws_account_id = get_aws_account_id()
    export("aws-account-id", aws_account_id)
    env = get_config_str("proj:env")

    export("env", env)

    # Create Resources Here
    bucket_name = f"{pulumi.get_stack()}.app.biotasker.com"
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
    _ = app_website_bucket.bucket_name.apply(
        lambda bucket_name: s3.BucketPolicy(
            append_resource_suffix("app-website"),
            bucket=bucket_name,
            policy_document=get_policy_document(
                statements=[
                    GetPolicyDocumentStatementArgs(
                        effect="Allow",
                        principals=[
                            GetPolicyDocumentStatementPrincipalArgs(
                                type="*",
                                identifiers=["*"],  # Allows all principals
                            )
                        ],
                        actions=["s3:GetObject"],
                        resources=[f"arn:aws:s3:::{bucket_name}/*"],
                    ),
                ]
            ).json,
        )
    )
    origin_id = "S3OriginMyBucket"
    app_cloudfront = app_website_bucket.website_url.apply(
        lambda full_url: cloudfront.Distribution(
            append_resource_suffix("app"),
            distribution_config=cloudfront.DistributionConfigArgs(
                price_class="PriceClass_100",
                origins=[
                    cloudfront.DistributionOriginArgs(
                        domain_name=full_url.removeprefix("http://"),
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
    )
    export("app-cloudfront-domain-name", app_cloudfront.domain_name)
