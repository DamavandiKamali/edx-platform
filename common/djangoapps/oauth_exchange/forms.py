"""
Forms to support third-party to first-party OAuth 2.0 access token exchange
"""
from django.contrib.auth.models import User
from django.forms import CharField
from oauth2_provider.constants import SCOPE_NAMES
import provider.constants
from provider.forms import OAuthForm, OAuthValidationError
from provider.oauth2.forms import ScopeChoiceField, ScopeMixin
from provider.oauth2.models import Client
from requests import HTTPError
import social.apps.django_app.utils as social_utils
from social.backends import oauth as social_oauth

from third_party_auth.provider import Registry
from third_party_auth import pipeline


class AccessTokenExchangeForm(ScopeMixin, OAuthForm):
    provider = CharField(required=False) # TODO: rename
    access_token = CharField(required=False)
    scope = ScopeChoiceField(choices=SCOPE_NAMES, required=False)
    client_id = CharField(required=False)

    def __init__(self, request, *args, **kwargs):
        super(AccessTokenExchangeForm, self).__init__(*args, **kwargs)
        self.request = request

    def _require_oauth_field(self, field_name):
        field_val = self.cleaned_data.get(field_name)
        if not field_val:
            raise OAuthValidationError(
                {
                    "error": "invalid_request",
                    "error_description": "{} is required".format(field_name),
                }
            )
        return field_val

    def clean_provider(self):
        return self._require_oauth_field("provider")

    def clean_access_token(self):
        return self._require_oauth_field("access_token")

    def clean_client_id(self):
        return self._require_oauth_field("client_id")

    def clean(self):
        if self._errors:
            return {}

        provider_name = self.cleaned_data["provider"]
        provider_class = Registry.get_by_backend_name(provider_name)
        if not (
                provider_class and
                issubclass(provider_class.BACKEND_CLASS, social_oauth.BaseOAuth2)
        ):
            raise OAuthValidationError(
                {
                    "error": "invalid_request",
                    "error_description": "{} is not a supported provider".format(provider_name),
                }
            )

        self.request.session[pipeline.AUTH_ENTRY_KEY] = pipeline.AUTH_ENTRY_API
        strategy = social_utils.load_strategy(
            request=self.request,
            backend=provider_class.BACKEND_CLASS.name
        )
        backend = strategy.backend

        client_id = self.cleaned_data["client_id"]
        try:
            client = Client.objects.get(client_id=client_id)
        except Client.DoesNotExist:
            raise OAuthValidationError(
                {
                    "error": "invalid_client",
                    "error_description": "{} is not a valid client_id".format(client_id),
                }
            )
        if client.client_type != provider.constants.PUBLIC:
            raise OAuthValidationError(
                {
                    "error": "unauthorized_client",
                    "error_description": "{} is not a public client".format(client_id),
                }
            )
        self.cleaned_data["client"] = client

        user = None
        try:
            user = backend.do_auth(self.cleaned_data.get("access_token"))
        except HTTPError as e:
            pass
        if user and isinstance(user, User):
            self.cleaned_data["user"] = user
        else:
            # Ensure user does not re-enter the pipeline
            strategy.clean_partial_pipeline()
            raise OAuthValidationError(
                {
                    "error": "invalid_grant",
                    "error_description": "access_token is not valid",
                }
            )

        return self.cleaned_data
