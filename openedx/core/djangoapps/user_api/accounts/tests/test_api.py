# -*- coding: utf-8 -*-
"""
Unit tests for behavior that is specific to the api methods (vs. the view methods).
Most of the functionality is covered in test_views.py.
"""

from django.test import TestCase
from student.tests.factories import UserFactory
from openedx.core.djangoapps.user_api.api.account import AccountUserNotFound, AccountUpdateError, AccountNotAuthorized
from ..api import get_account_settings, update_account_settings

class TestAccountApi(TestCase):
    password = "test"

    def setUp(self):
        super(TestAccountApi, self).setUp()
        self.user = UserFactory.create(password=self.password)
        self.different_user = UserFactory.create(password=self.password)
        self.staff_user = UserFactory(is_staff=True, password=self.password)

    def test_get_username_provided(self):
        """Test the difference in behavior when a username is supplied to get_account_settings."""
        account_settings = get_account_settings(self.user)
        self.assertEqual(self.user.username, account_settings["username"])

        account_settings = get_account_settings(self.user, username=self.user.username)
        self.assertEqual(self.user.username, account_settings["username"])

        account_settings = get_account_settings(self.user, username=self.different_user.username)
        self.assertEqual(self.different_user.username, account_settings["username"])

    def test_get_configuration_provided(self):
        """Test the difference in behavior when a configuration is supplied to get_account_settings."""
        config = {
            "default_visibility": "private",

            "shareable_fields": [
                'name',
            ],

            "public_fields": [
                'email',
            ],
        }

        # With default configuration settings, email is not shared with other (non-staff) users.
        account_settings = get_account_settings(self.user, self.different_user.username)
        self.assertFalse("email" in account_settings)

        account_settings = get_account_settings(self.user, self.different_user.username, configuration=config)
        self.assertEqual(self.different_user.email, account_settings["email"])

    def test_get_user_not_found(self):
        """Test that AccountUserNotFound is thrown if there is no user with username."""
        with self.assertRaises(AccountUserNotFound):
            get_account_settings(self.user, username="does_not_exist")

        self.user.username = "does_not_exist"
        with self.assertRaises(AccountUserNotFound):
            get_account_settings(self.user)

    def test_update_username_provided(self):
        """Test the difference in behavior when a username is supplied to update_account_settings."""
        update_account_settings(self.user, {"name": "Mickey Mouse"})
        account_settings = get_account_settings(self.user)
        self.assertEqual("Mickey Mouse", account_settings["name"])

        update_account_settings(self.user, {"name": "Donald Duck"}, username=self.user.username)
        account_settings = get_account_settings(self.user)
        self.assertEqual("Donald Duck", account_settings["name"])

        with self.assertRaises(AccountNotAuthorized):
            update_account_settings(self.different_user, {"name": "Pluto"}, username=self.user.username)

    def test_update_user_not_found(self):
        """Test that AccountUserNotFound is thrown if there is no user with username."""
        with self.assertRaises(AccountUserNotFound):
            update_account_settings(self.user, {}, username="does_not_exist")

        self.user.username = "does_not_exist"
        with self.assertRaises(AccountUserNotFound):
            update_account_settings(self.user, {})

    def test_update_error_updating(self):
        """Test that AccountUpdateError is thrown if incorrect values are supplied."""
        with self.assertRaises(AccountUpdateError):
            update_account_settings(self.user, {"username": "not_allowed"})

        with self.assertRaises(AccountUpdateError):
            update_account_settings(self.user, {"gender": "undecided"})
