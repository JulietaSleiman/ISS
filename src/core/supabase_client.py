"""Small HTTPS transport shared by authentication and the pending-close uploader."""
import json
import socket
import urllib.error
import urllib.request

from src.core import app_config


class SupabaseError(Exception):
    pass


class AuthError(SupabaseError):
    pass


class NetworkError(SupabaseError):
    pass


class ConfigError(SupabaseError):
    pass


def request(method, path, payload=None, access_token=None, headers=None):
    if not app_config.SUPABASE_URL.startswith('https://') or not app_config.SUPABASE_PUBLISHABLE_KEY.startswith('sb_publishable_'):
        raise ConfigError('La configuración de Supabase no es válida.')
    if not path.startswith('/') or path.startswith('//'):
        raise ConfigError('Ruta de Supabase no válida.')
    request_headers = {'apikey': app_config.SUPABASE_PUBLISHABLE_KEY, 'Content-Type': 'application/json'}
    if access_token:
        request_headers['Authorization'] = f'Bearer {access_token}'
    if headers:
        request_headers.update(headers)
    body = json.dumps(payload, allow_nan=False).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(app_config.SUPABASE_URL + path, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        # Never expose server bodies: they may include account information.
        code = exc.code
        exc.close()
        if code in (400, 401, 403):
            raise AuthError('Acceso rechazado. Revise usuario, contraseña y permisos de la sucursal.') from None
        if code >= 500:
            raise NetworkError('Supabase no está disponible temporalmente.') from None
        raise SupabaseError(f'Supabase respondió con error {code}. Revise la configuración del proyecto.') from None
    except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, OSError):
        raise NetworkError('No se pudo conectar con Supabase.') from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise SupabaseError('Supabase devolvió una respuesta no válida.') from None
