"""Supabase Auth explicitly returns403 bad_jwt; it is not a network outage."""
import unittest
from unittest.mock import patch
from urllib.request import Request
from email.message import Message
from urllib.error import HTTPError
from backend.supabase import BackendError,http_json

class AuthErrorTests(unittest.TestCase):
    def test_auth_bad_jwt_statuses_are_invalid_credentials(self):
        for status in (400,401,403):
            with self.subTest(status=status),patch('backend.supabase.build_opener') as opener:
                url='https://fixture.supabase.co/auth/v1/user'
                opener.return_value.open.side_effect=HTTPError(url,status,'labelled Auth fixture',Message(),None)
                with self.assertRaises(BackendError) as failure:http_json(Request(url),1)
                self.assertEqual((failure.exception.status,failure.exception.code),(401,'invalid_token'))
    def test_repository403_and_provider500_are_not_mislabelled_auth(self):
        for path,status in [('/rest/v1/recheck_workspaces',403),('/auth/v1/user',500)]:
            with self.subTest(path=path,status=status),patch('backend.supabase.build_opener') as opener:
                url='https://fixture.supabase.co'+path
                opener.return_value.open.side_effect=HTTPError(url,status,'labelled upstream fixture',Message(),None)
                with self.assertRaises(BackendError) as failure:http_json(Request(url),1)
                self.assertEqual((failure.exception.status,failure.exception.code),(503,'upstream_unavailable'))
