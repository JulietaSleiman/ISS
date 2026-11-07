"""Windows-user protected offline credentials (DPAPI); no plaintext fallback."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import tempfile

from src.core import app_config
from src.db import database


class CredentialStoreError(Exception):
    pass


class _Blob(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(data, decrypt=False):
    if os.name != 'nt':
        raise CredentialStoreError('El acceso sin conexión requiere la protección de credenciales de Windows.')
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = _Blob(len(data), buffer)
    target = _Blob()
    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    protect = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    protect.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p,
                        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
    protect.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if not protect(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise CredentialStoreError('No se pudo acceder a las credenciales protegidas de Windows.')
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(target.pbData, ctypes.c_void_p))


def protect(data):
    return _crypt(data)


def unprotect(data):
    return _crypt(data, decrypt=True)


def _path(username, branch_id=None):
    if branch_id is None:
        from src.core.installation_store import get_installation
        installation = get_installation()
        if installation is None:
            raise CredentialStoreError('Esta computadora todavía no está vinculada a una sucursal.')
        branch_id = installation['branch_id']
    identity = f'{app_config.SUPABASE_URL}|{branch_id}|{username}'
    name = hashlib.sha256(identity.encode()).hexdigest()
    return Path(database.DB_DIR) / 'auth_cache' / f'{name}.bin'


def save(username, data):
    target = _path(username, data['branch'])
    encrypted = protect(json.dumps(data, allow_nan=False).encode())
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
            temp_name = temporary.name
            temporary.write(encrypted)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temp_name, target)
    except OSError as exc:
        raise CredentialStoreError('No se pudieron guardar las credenciales protegidas.') from exc
    finally:
        if temp_name and Path(temp_name).exists():
            Path(temp_name).unlink()


def load(username, branch_id=None):
    target = _path(username, branch_id)
    try:
        return json.loads(unprotect(target.read_bytes()))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, CredentialStoreError):
        raise CredentialStoreError('Las credenciales locales no están disponibles. Inicie sesión con internet.') from None


def delete(username, branch_id=None):
    try:
        _path(username, branch_id).unlink(missing_ok=True)
    except OSError as exc:
        raise CredentialStoreError('No se pudo revocar el acceso local de este usuario.') from exc
