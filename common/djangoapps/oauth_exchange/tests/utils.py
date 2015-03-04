import json

from django.contrib.sessions.middleware import SessionMiddleware
from django.test.client import RequestFactory
import httpretty
import provider.constants
from provider.oauth2.models import Client
from social.apps.django_app.default.models import UserSocialAuth

from student.tests.factories import UserFactory


class AccessTokenExchangeTestMixin(object):
    def setUp(self):
        super(AccessTokenExchangeTestMixin, self).setUp()

        self.client_id = "test_client_id"
        self.oauth_client = Client.objects.create(
            client_id=self.client_id,
            client_type=provider.constants.PUBLIC
        )
        self.social_uid = "test_social_uid"
        self.user = UserFactory()
        UserSocialAuth.objects.create(user=self.user, provider=self.PROVIDER, uid=self.social_uid)
        self.request = RequestFactory().post("dummy_url")
        SessionMiddleware().process_request(self.request)
        self.access_token = "test_access_token"
        # Initialize to minimal data
        self.data = {
            "provider": self.PROVIDER,
            "access_token": self.access_token,
            "client_id": self.client_id,
        }

    def _setup_user_response(self, success):
        """
        Register a mock response for the third party user information endpoint;
        success indicates whether the response status code should be 200 or 400
        """
        if success:
            status = 200
            body = json.dumps({self.UID_FIELD: self.social_uid})
        else:
            status = 400
            body = json.dumps({})
        httpretty.register_uri(
            httpretty.GET,
            self.USER_URL,
            body=body,
            status=status,
            content_type="application/json"
        )

    def test_minimal(self):
        self._setup_user_response(success=True)
        self._assert_success(self.data, expected_scopes=[])

    def test_scopes(self):
        self._setup_user_response(success=True)
        self.data["scope"] = "profile email"
        self._assert_success(self.data, expected_scopes=["profile", "email"])

    def test_missing_fields(self):
        for field in ["provider", "access_token", "client_id"]:
            data = dict(self.data)
            del data[field]
            self._assert_error(data, "invalid_request", "{} is required".format(field))

    def test_invalid_provider(self):
        self.data["provider"] = "nonexistent_provider"
        self._assert_error(
            self.data,
            "invalid_request",
            "nonexistent_provider is not a supported provider"
        )

    def test_invalid_client(self):
        self.data["client_id"] = "nonexistent_client"
        self._assert_error(
            self.data,
            "invalid_client",
            "nonexistent_client is not a valid client_id"
        )

    def test_confidential_client(self):
        self.oauth_client.client_type = provider.constants.CONFIDENTIAL
        self.oauth_client.save()
        self._assert_error(
            self.data,
            "unauthorized_client",
            "test_client_id is not a public client"
        )

    def test_invalid_acess_token(self):
        self._setup_user_response(success=False)
        self._assert_error(self.data, "invalid_grant", "access_token is not valid")

    def test_no_linked_user(self):
        UserSocialAuth.objects.all().delete()
        self._setup_user_response(success=True)
        self._assert_error(self.data, "invalid_grant", "access_token is not valid")


class AccessTokenExchangeMixinFacebook(object):
    """Tests access token exchange with the Facebook backend"""
    PROVIDER="facebook"
    USER_URL = "https://graph.facebook.com/me"
    UID_FIELD = "id"


class AccessTokenExchangeMixinGoogle(object):
    """Tests access token exchange with the Google backend"""
    PROVIDER = "google-oauth2"
    USER_URL = "https://www.googleapis.com/oauth2/v1/userinfo"
    UID_FIELD = "email"
