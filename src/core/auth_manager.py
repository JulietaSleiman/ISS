"""Online Supabase identities with bounded, previously verified offline access."""
from dataclasses import asdict, dataclass
import hashlib
import hmac
import re
import secrets
import threading
import time
from urllib.parse import quote

from src.core import app_config, credential_store, supabase_client
from src.core.supabase_client import AuthError, ConfigError, NetworkError
from src.core.installation_store import LEGACY_SIMOCA_ID, bind_verified, get_installation, normalize_branch_code


@dataclass
class UserSession:
    user_id: str
    username: str
    branch_id: str
    branch_name: str
    role: str
    access_token: str = ''
    refresh_token: str = ''
    offline: bool = False


def normalize_username(username):
    if not isinstance(username,str):
        raise AuthError('Ingrese un usuario válido, por ejemplo caja1.')
    username = ''.join(username.lower().split())
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,49}', username):
        raise AuthError('Ingrese un usuario válido, por ejemplo caja1.')
    return username


def technical_email(username, branch_code=None):
    if branch_code is None:
        installation = get_installation()
        if installation is None:
            raise ConfigError('Ingrese el código de sucursal para vincular esta computadora por primera vez.')
        branch_code = installation['branch_code']
    return f'{normalize_username(username)}.{normalize_branch_code(branch_code)}@usuarios.invalid'


def _derive(password, salt):
    return hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


class AuthManager:
    _session = None
    _expires_at = 0
    _cache = None
    _lock = threading.RLock()
    cache_warning = ''

    @classmethod
    def current_user(cls):
        return cls._session

    @classmethod
    def require_user(cls):
        if cls._session is None:
            raise AuthError('Debe iniciar sesión para realizar esta operación.')
        return cls._session

    @classmethod
    def _validate_identity(cls, result, username, branch_code, installation=None):
        token = result.get('access_token')
        user_id = result.get('user', {}).get('id')
        if not token or not user_id:
            raise AuthError('No se pudo verificar la identidad del usuario.')
        profiles = supabase_client.request('GET', f'/rest/v1/profiles?id=eq.{quote(user_id)}&select=id,username,sucursal_id,nombre,rol,activo', access_token=token)
        if not profiles or len(profiles) != 1:
            raise AuthError('El usuario no tiene una sucursal asignada. Contacte al administrador.')
        profile = profiles[0]
        if profile['id'] != user_id or not profile['activo'] or not profile.get('sucursal_id') or profile['username'] != username or profile['rol'] not in ('cajero', 'admin'):
            raise AuthError('El usuario no está habilitado para esta sucursal.')
        branch_id = profile['sucursal_id']
        if installation and branch_id != installation['branch_id']:
            raise AuthError('El usuario pertenece a otra sucursal. Esta instalación conserva su asignación original.')
        branches = supabase_client.request('GET', f'/rest/v1/sucursales?id=eq.{quote(branch_id)}&select=*', access_token=token)
        if not branches or len(branches) != 1 or branches[0].get('id') != branch_id or not branches[0]['activa']:
            raise AuthError('La sucursal no está habilitada.')
        if not branches[0].get('codigo'):
            raise ConfigError('La sucursal no tiene un código configurado. Ejecute la migración 007 y configure su código en Supabase.')
        if normalize_branch_code(branches[0]['codigo']) != branch_code:
            raise AuthError('El código ingresado no coincide con la sucursal asignada al usuario.')
        return UserSession(user_id, username, branch_id, branches[0]['nombre'], profile['rol'], token, result.get('refresh_token', ''))

    @classmethod
    def _persist(cls, cache):
        cls.cache_warning = ''
        try:
            credential_store.save(cache['session']['username'], cache)
        except (credential_store.CredentialStoreError, OSError):
            # A previous password must not remain usable offline after an online
            # login with a changed password that could not update this cache.
            credential_store.delete(cache['session']['username'], cache['branch'])
            cls.cache_warning = 'Sesión iniciada con internet. No se pudo habilitar el acceso sin conexión en este Windows.'

    @classmethod
    def login(cls, username, password, branch_code=None):
        with cls._lock:
            cls._session = None
            cls._cache = None
            cls.cache_warning = ''
            username = normalize_username(username)
            if not password:
                raise AuthError('Ingrese la contraseña.')
            installation = get_installation()
            if installation and installation['project_url'] != app_config.SUPABASE_URL:
                raise ConfigError('Esta instalación pertenece a otro proyecto de Supabase. Revise la configuración.')
            if branch_code is None:
                if installation is None:
                    raise ConfigError('Ingrese el código de sucursal para vincular esta computadora por primera vez.')
                branch_code = installation['branch_code']
            branch_code = normalize_branch_code(branch_code)
            if installation and branch_code != installation['branch_code']:
                raise AuthError('Esta computadora ya está vinculada a otra sucursal; no se cambiará su código.')
            try:
                result = supabase_client.request('POST', '/auth/v1/token?grant_type=password', {'email': technical_email(username,branch_code), 'password': password})
                session = cls._validate_identity(result, username, branch_code, installation)
            except AuthError:
                if installation:
                    credential_store.delete(username,installation['branch_id'])
                raise
            except NetworkError:
                if installation is None:
                    raise AuthError('El primer ingreso a esta computadora requiere internet para verificar la sucursal.') from None
                cache = credential_store.load(username,installation['branch_id'])
                if not cache or cache.get('project') != app_config.SUPABASE_URL or cache.get('branch') != installation['branch_id'] or cache.get('session', {}).get('username') != username:
                    raise AuthError('Este usuario necesita iniciar sesión con internet por primera vez.') from None
                cached_code = cache.get('branch_code')
                simoca_legacy_scope = installation['branch_id'] == LEGACY_SIMOCA_ID and branch_code == 'estacion-de-simoca'
                if cached_code != branch_code and not (cached_code is None and (installation['legacy'] or simoca_legacy_scope)):
                    raise AuthError('Las credenciales locales pertenecen a otro código de sucursal.') from None
                now = time.time()
                if now < cache['verified_at'] or now - cache['verified_at'] > app_config.OFFLINE_DAYS * 86400:
                    raise AuthError('El permiso sin conexión venció. Conecte internet para renovarlo.') from None
                if not hmac.compare_digest(_derive(password, cache['salt']), cache['verifier']):
                    raise AuthError('Usuario o contraseña incorrectos.') from None
                session = UserSession(**cache['session'])
                if session.branch_id != installation['branch_id'] or session.role not in ('cajero', 'admin'):
                    raise AuthError('La identidad local no es válida.')
                # Migrate only installation metadata while offline. The protected
                # old verifier remains untouched until an online refresh verifies
                # identity again; a DPAPI write failure must not revoke it.
                # Manually configured non-Simoca legacy scopes keep their old
                # binding until online migration rather than losing that context.
                if cached_code is not None or simoca_legacy_scope:
                    bind_verified(session.branch_id,branch_code,session.branch_name,app_config.SUPABASE_URL)
                cache['branch_code'] = branch_code
                session.access_token = ''
                session.offline = True
                cls._expires_at = 0
                cls._session, cls._cache = session, cache
                return session
            salt = secrets.token_hex(16)
            bind_verified(session.branch_id,branch_code,session.branch_name,app_config.SUPABASE_URL)
            cache = {'project': app_config.SUPABASE_URL, 'branch': session.branch_id, 'branch_code':branch_code,
                     'verified_at': time.time(), 'salt': salt, 'verifier': _derive(password, salt),
                     'session': asdict(session)}
            cls._persist(cache)
            cls._expires_at = time.time() + int(result.get('expires_in', 3600))
            cls._session, cls._cache = session, cache
            return session

    @classmethod
    def ensure_auth_token(cls):
        with cls._lock:
            session = cls.require_user()
            installation = get_installation()
            if not installation or installation['branch_id'] != session.branch_id or installation['project_url'] != app_config.SUPABASE_URL:
                raise ConfigError('La sesión no coincide con la instalación vinculada. Revise la configuración.')
            if session.access_token and time.time() < cls._expires_at - 60:
                return session.access_token
            if not session.refresh_token:
                raise AuthError('Inicie sesión con internet para sincronizar.')
            try:
                result = supabase_client.request('POST', '/auth/v1/token?grant_type=refresh_token', {'refresh_token': session.refresh_token})
                refreshed = cls._validate_identity(result, session.username, installation['branch_code'], installation)
                if refreshed.user_id != session.user_id:
                    raise AuthError('La identidad de la sesión cambió. Vuelva a iniciar sesión.')
            except AuthError:
                credential_store.delete(session.username,session.branch_id)
                cls._session = None
                cls._cache = None
                raise
            cls._expires_at = time.time() + int(result.get('expires_in', 3600))
            cls._session = refreshed
            if cls._cache:
                cls._cache['session'] = asdict(refreshed)
                cls._cache['verified_at'] = time.time()
                cls._persist(cls._cache)
            return refreshed.access_token

    @classmethod
    def logout(cls):
        with cls._lock:
            cls._session = None
            cls._cache = None
            cls._expires_at = 0
            cls.cache_warning = ''
