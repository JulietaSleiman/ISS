import copy
import io
import json
import os
from contextlib import closing
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from src.core import app_config, credential_store, supabase_client
from src.core.auth_manager import AuthManager, technical_email
from src.core.supabase_client import AuthError, NetworkError, SupabaseError
from src.db import database
from src.core.installation_store import bind_verified


class AuthTests(unittest.TestCase):
    def setUp(self):
        AuthManager.logout()
        self.addCleanup(AuthManager.logout)
        temporary = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(temporary.cleanup)
        for target,value in (('src.db.database.DB_PATH',Path(temporary.name)/'test.sqlite'),
                             ('src.db.database.DB_DIR',Path(temporary.name)),
                             ('src.db.database.auto_backup_db',lambda:None)):
            patcher=patch(target,value);patcher.start();self.addCleanup(patcher.stop)
        database.init_db()
        bind_verified(app_config.BRANCH_ID,app_config.BRANCH_CODE,app_config.BRANCH_NAME,app_config.SUPABASE_URL)
        self.cache = {}
        for method, replacement in (
            ('save', lambda name, data: self.cache.update({name: copy.deepcopy(data)})),
            ('load', lambda name, branch_id=None: copy.deepcopy(self.cache.get(name))),
            ('delete', lambda name, branch_id=None: self.cache.pop(name, None)),
        ):
            patcher = patch.object(credential_store, method, side_effect=replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def responses(self, active=True, branch=None, token='token'):
        return [
            {'access_token': token, 'refresh_token': 'refresh', 'expires_in': 3600,
             'user': {'id': '59150992-f734-4b60-af9a-c8ed9b428db3'}},
            [{'id': '59150992-f734-4b60-af9a-c8ed9b428db3', 'username': 'caja1',
              'sucursal_id': branch or app_config.BRANCH_ID, 'nombre': 'Caja 1',
              'rol': 'cajero', 'activo': active}],
            [{'id': app_config.BRANCH_ID, 'codigo':app_config.BRANCH_CODE, 'nombre': app_config.BRANCH_NAME, 'activa': True}],
        ]

    def online_login(self):
        with patch.object(supabase_client, 'request', side_effect=self.responses()):
            return AuthManager.login('caja 1', 'correct-password')

    def test_online_alias_login_and_branch_checked_before_caching(self):
        with patch.object(supabase_client, 'request', side_effect=self.responses()) as request:
            session = AuthManager.login('caja 1', 'correct-password')
        self.assertEqual(session.username, 'caja1')
        self.assertEqual(session.branch_id, app_config.BRANCH_ID)
        self.assertFalse(session.offline)
        self.assertEqual(request.call_args_list[0].args[2]['email'], 'caja1.estacion-de-simoca@usuarios.invalid')
        self.assertNotIn('correct-password', json.dumps(self.cache))

    def test_cached_user_can_login_offline_but_wrong_password_is_rejected(self):
        self.online_login()
        AuthManager.logout()
        with patch.object(supabase_client, 'request', side_effect=NetworkError('offline')):
            self.assertTrue(AuthManager.login('caja1', 'correct-password').offline)
            self.assertEqual(AuthManager.current_user().access_token, '')
            with self.assertRaises(AuthError):
                AuthManager.login('caja1', 'wrong')
        self.assertIsNone(AuthManager.current_user())

    def test_first_login_without_connection_is_rejected(self):
        with patch.object(supabase_client, 'request', side_effect=NetworkError('offline')):
            with self.assertRaisesRegex(AuthError, 'primera vez'):
                AuthManager.login('caja1', 'correct-password')

    def test_explicit_online_rejection_invalidates_cached_offline_permission(self):
        self.online_login()
        with patch.object(supabase_client, 'request', side_effect=AuthError('rejected')):
            with self.assertRaises(AuthError):
                AuthManager.login('caja1', 'correct-password')
        self.assertNotIn('caja1', self.cache)
        self.assertIsNone(AuthManager.current_user())

    def test_inactive_user_and_other_branch_do_not_get_cached(self):
        for responses in (self.responses(active=False), self.responses(branch='other-branch')):
            with self.subTest(profile=responses[1]):
                with patch.object(supabase_client, 'request', side_effect=responses):
                    with self.assertRaises(AuthError):
                        AuthManager.login('caja1', 'correct-password')
                self.assertFalse(self.cache)

    def test_foreign_cache_project_branch_and_expired_cache_are_rejected(self):
        self.online_login()
        original = copy.deepcopy(self.cache)
        for field, value in (('project', 'https://foreign.supabase.co'), ('branch', 'other'), ('verified_at', 0)):
            with self.subTest(field=field):
                self.cache = copy.deepcopy(original)
                self.cache['caja1'][field] = value
                with patch.object(supabase_client, 'request', side_effect=NetworkError('offline')):
                    with self.assertRaises(AuthError):
                        AuthManager.login('caja1', 'correct-password')

    def test_permission_failure_during_profile_read_never_falls_back(self):
        self.online_login()
        with patch.object(supabase_client, 'request', side_effect=[self.responses()[0], AuthError('forbidden')]):
            with self.assertRaises(AuthError):
                AuthManager.login('caja1', 'correct-password')
        self.assertFalse(self.cache)

    def test_refresh_restores_online_identity_and_updates_protected_cache(self):
        self.online_login()
        with patch.object(supabase_client, 'request', side_effect=NetworkError('offline')):
            AuthManager.login('caja1', 'correct-password')
        with patch.object(supabase_client, 'request', side_effect=self.responses(token='new-token')):
            self.assertEqual(AuthManager.ensure_auth_token(), 'new-token')
        self.assertFalse(AuthManager.current_user().offline)
        self.assertEqual(self.cache['caja1']['session']['access_token'], 'new-token')

    def test_revoked_refresh_invalidates_identity_and_offline_cache(self):
        self.online_login()
        AuthManager._expires_at = 0
        with patch.object(supabase_client, 'request', side_effect=AuthError('revoked')):
            with self.assertRaises(AuthError):
                AuthManager.ensure_auth_token()
        self.assertFalse(self.cache)
        self.assertIsNone(AuthManager.current_user())

    def test_online_login_survives_store_failure_with_visible_warning(self):
        self.online_login()
        self.assertIn('caja1', self.cache)
        with patch.object(credential_store, 'save', side_effect=credential_store.CredentialStoreError('blocked')):
            self.assertFalse(self.online_login().offline)
        self.assertTrue(AuthManager.cache_warning)
        self.assertNotIn('caja1', self.cache)


class TransportTests(unittest.TestCase):
    def test_transport_timeout_and_connection_errors_allow_offline_recovery(self):
        for error in (TimeoutError('timeout'), urllib.error.URLError('no connection')):
            with self.subTest(error=error):
                with patch('urllib.request.urlopen', side_effect=error):
                    with self.assertRaises(NetworkError):
                        supabase_client.request('POST', '/auth/v1/token?grant_type=password', {'email': 'example@usuarios.invalid'})

    def test_only_network_and_5xx_errors_are_retriable(self):
        for code in (400, 401, 403, 404, 429, 500, 503):
            with self.subTest(code=code):
                error = urllib.error.HTTPError('https://example.invalid', code, 'error', {}, io.BytesIO(b'private-server-body'))
                expected = AuthError if code in (400, 401, 403) else NetworkError if code >= 500 else SupabaseError
                with patch('urllib.request.urlopen', side_effect=error):
                    with self.assertRaises(expected) as caught:
                        supabase_client.request('GET', '/rest/v1/profiles')
                self.assertNotIn('private-server-body', str(caught.exception))
                self.assertTrue(error.closed)

    def test_publishable_key_is_not_used_as_jwt(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'[]'
        with patch('urllib.request.urlopen', return_value=response) as send:
            supabase_client.request('GET', '/rest/v1/profiles')
        request = send.call_args.args[0]
        self.assertEqual(request.get_header('Apikey'), app_config.SUPABASE_PUBLISHABLE_KEY)
        self.assertIsNone(request.get_header('Authorization'))

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI')
    def test_windows_protected_credentials_roundtrip_and_tampering(self):
        protected = credential_store.protect(b'not-a-real-token')
        self.assertNotIn(b'not-a-real-token', protected)
        self.assertEqual(credential_store.unprotect(protected), b'not-a-real-token')
        corrupted = protected[:-1] + bytes([protected[-1] ^ 1])
        with self.assertRaises(credential_store.CredentialStoreError):
            credential_store.unprotect(corrupted)


if __name__ == '__main__':
    unittest.main()
