import pytest
from faker import Faker

from .helpers import rendered_answers
from .helpers import validate_answers


class TestWhenRedirectBareDomainToAppDomainAnsweredYes:
    def test_Given_app_domain_without_www__Then_copier_rejects_the_answer(self, faker: Faker) -> None:
        with pytest.raises(ValueError, match="redirect_bare_domain_to_app_domain"):
            validate_answers(app_domain_name=faker.domain_name(), redirect_bare_domain_to_app_domain=True)

    def test_Given_www_app_domain__Then_the_answer_is_kept(self, faker: Faker) -> None:
        answers = rendered_answers(
            app_domain_name=f"www.{faker.domain_name()}", redirect_bare_domain_to_app_domain=True
        )

        assert answers["redirect_bare_domain_to_app_domain"] is True


class TestWhenRedirectBareDomainToAppDomainLeftUnanswered:
    @pytest.mark.parametrize(
        ("www_prefix", "expected_redirect"),
        [
            pytest.param("www.", True, id="www-domain-defaults-to-redirect"),
            pytest.param("", False, id="domain-without-www-has-no-bare-domain"),
        ],
    )
    def test_Then_it_defaults_to_whether_app_domain_starts_with_www(
        self, faker: Faker, www_prefix: str, expected_redirect: bool
    ) -> None:
        answers = rendered_answers(app_domain_name=f"{www_prefix}{faker.domain_name()}")

        assert answers["redirect_bare_domain_to_app_domain"] is expected_redirect
