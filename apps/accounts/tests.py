from django.test import TestCase
from django.urls import reverse


class AccountsUrlTests(TestCase):
    def test_login_route_is_available_with_accounts_namespace(self):
        self.assertEqual(reverse('accounts:login'), '/accounts/login/')
