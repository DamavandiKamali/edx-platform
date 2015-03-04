from datetime import timedelta
import json
import mock
import unittest

from django.conf import settings
from django.core.urlresolvers import reverse
from django.test import TestCase
import httpretty
import provider.constants
from provider import scope
from provider.oauth2.models import AccessToken

from oauth_exchange.tests.utils import (
    AccessTokenExchangeTestMixin,
    AccessTokenExchangeMixinFacebook,
    AccessTokenExchangeMixinGoogle
)


class AccessTokenExchangeViewTest(AccessTokenExchangeTestMixin):
    def setUp(self):
        super(AccessTokenExchangeViewTest, self).setUp()
        self.url = reverse("exchange_oauth_token")

    def _assert_error(self, data, expected_error, expected_error_description):
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(
            json.loads(response.content),
            {"error": expected_error, "error_description": expected_error_description}
        )
        self.assertNotIn("partial_pipeline", self.client.session)

    def _assert_success(self, data, expected_scopes):
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        content = json.loads(response.content)
        self.assertEqual(set(content.keys()), {"access_token", "token_type", "expires_in", "scope"})
        self.assertEqual(content["token_type"], "Bearer")
        self.assertLessEqual(
            timedelta(seconds=int(content["expires_in"])),
            provider.constants.EXPIRE_DELTA_PUBLIC
        )
        self.assertEqual(content["scope"], " ".join(expected_scopes))
        token = AccessToken.objects.get(token=content["access_token"])
        self.assertEqual(token.user, self.user)
        self.assertEqual(token.client, self.oauth_client)
        self.assertEqual(scope.to_names(token.scope), expected_scopes)

    def test_single_access_token(self):
        def extract_token(response):
            return json.loads(response.content)["access_token"]

        self._setup_user_response(success=True)
        for single_access_token in [True, False]:
            with mock.patch(
                    "oauth_exchange.views.constants.SINGLE_ACCESS_TOKEN",
                    single_access_token
            ):
                first_response = self.client.post(self.url, self.data)
                second_response = self.client.post(self.url, self.data)
                self.assertEqual(
                    extract_token(first_response) == extract_token(second_response),
                    single_access_token
                )

    def test_get_method(self):
        response = self.client.get(self.url, self.data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content),
            {
                "error": "invalid_request",
                "error_description": "Only POST requests allowed.",
            }
        )

# This is necessary because cms does not implement third party auth
@unittest.skipUnless(settings.FEATURES.get("ENABLE_THIRD_PARTY_AUTH"), "third party auth not enabled")
@httpretty.activate
class AccessTokenExchangeViewTestFacebook(
        AccessTokenExchangeViewTest,
        AccessTokenExchangeMixinFacebook,
        TestCase
):
    pass


# This is necessary because cms does not implement third party auth
@unittest.skipUnless(settings.FEATURES.get("ENABLE_THIRD_PARTY_AUTH"), "third party auth not enabled")
@httpretty.activate
class AccessTokenExchangeViewTestGoogle(
        AccessTokenExchangeViewTest,
        AccessTokenExchangeMixinGoogle,
        TestCase
):
    pass
