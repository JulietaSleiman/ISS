"""Vinculación durable de una instalación; nunca cambia de sucursal por defecto."""
from contextlib import closing
import os
import re
from uuid import UUID

from src.core import app_config
from src.core.supabase_client import ConfigError
from src.db import database

LEGACY_SIMOCA_ID = 'f2985c88-2a4e-4e73-92d5-85d905b3db41'


def normalize_branch_code(code):
    if not isinstance(code, str):
        raise ConfigError('Ingrese el código de sucursal asignado por administración.')
    code = code.strip().lower()
    if len(code) > 48 or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', code):
        raise ConfigError('El código debe contener letras sin acentos, números y guiones; máximo 48 caracteres.')
    return code


def _uuid(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ConfigError('La identidad de sucursal no es válida. Revise la instalación.') from None


def _has_table(conn, table):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _read(conn):
    settings = {}
    if _has_table(conn, 'sync_configuracion'):
        settings = {row['key']: row['value'] for row in conn.execute('SELECT key,value FROM sync_configuracion')}
    known = set()
    if settings.get('sucursal_id'):
        known.add(_uuid(settings['sucursal_id']))
    for table in ('caja_sesiones','sync_cierres','sync_entidades','caja_regularizaciones'):
        if not _has_table(conn, table):
            continue
        columns = {row['name'] for row in conn.execute(f'PRAGMA table_info({table})')}
        if 'sucursal_id' in columns:
            for row in conn.execute(f"SELECT DISTINCT sucursal_id FROM {table} WHERE sucursal_id IS NOT NULL AND sucursal_id<>''"):
                known.add(_uuid(row['sucursal_id']))
    if len(known) > 1:
        raise ConfigError('La base local contiene datos de distintas sucursales. No se permite vincularla automáticamente.')
    return settings, next(iter(known), None)


def get_installation():
    if not database.DB_PATH.exists():
        return None
    with closing(database.get_connection()) as conn:
        settings, branch_id = _read(conn)
    metadata_keys = ('codigo_sucursal','nombre_sucursal','supabase_url')
    if any(key in settings for key in metadata_keys):
        if branch_id is None or not all(settings.get(key) for key in metadata_keys):
            raise ConfigError('La configuración local de sucursal está incompleta. Revise la instalación; no se reasignará automáticamente.')
        project = settings['supabase_url'].rstrip('/')
        if not project.startswith('https://') or project != app_config.SUPABASE_URL:
            raise ConfigError('Esta instalación pertenece a otro proyecto de Supabase. Revise la configuración.')
        if not settings['nombre_sucursal'].strip():
            raise ConfigError('El nombre guardado de la sucursal no es válido.')
        return {'branch_id':branch_id,'branch_code':normalize_branch_code(settings['codigo_sucursal']),
                'branch_name':settings['nombre_sucursal'],'project_url':project,'legacy':False}
    if branch_id is None:
        return None
    project = (settings.get('supabase_url') or app_config.SUPABASE_URL).rstrip('/')
    # Compatibility only when a real binding/history already identifies Simoca.
    # Changing compile-time defaults never assigns an otherwise fresh database.
    if branch_id == LEGACY_SIMOCA_ID:
        return {'branch_id':branch_id,'branch_code':'estacion-de-simoca',
                'branch_name':settings.get('nombre_sucursal') or 'Estación de Simoca',
                'project_url':project,'legacy':True}
    if os.environ.get('ISS_BRANCH_ID') and os.environ.get('ISS_BRANCH_CODE') and _uuid(os.environ['ISS_BRANCH_ID']) == branch_id:
        return {'branch_id':branch_id,'branch_code':normalize_branch_code(os.environ['ISS_BRANCH_CODE']),
                'branch_name':os.environ.get('ISS_BRANCH_NAME',branch_id),'project_url':project,'legacy':True}
    return None  # Unknown old binding requires an online, explicitly entered code.


def bind_verified(branch_id, branch_code, branch_name, project_url):
    branch_id = _uuid(branch_id)
    branch_code = normalize_branch_code(branch_code)
    project_url = project_url.rstrip('/')
    if not isinstance(branch_name,str) or not branch_name.strip() or not project_url.startswith('https://'):
        raise ConfigError('Los datos verificados de la instalación no son válidos.')
    with closing(database.get_connection()) as conn:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            settings, known_id = _read(conn)
            if known_id and known_id != branch_id:
                raise ConfigError('Esta base local ya pertenece a otra sucursal. Use una instalación separada.')
            if settings.get('supabase_url') and settings['supabase_url'].rstrip('/') != project_url:
                raise ConfigError('Esta base local ya pertenece a otro proyecto de Supabase.')
            if 'codigo_sucursal' in settings and normalize_branch_code(settings['codigo_sucursal']) != branch_code:
                raise ConfigError('Esta instalación ya tiene otro código de sucursal asignado.')
            conn.execute('CREATE TABLE IF NOT EXISTS sync_configuracion (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
            for key, value in (('sucursal_id',branch_id),('codigo_sucursal',branch_code),
                               ('nombre_sucursal',branch_name.strip()),('supabase_url',project_url)):
                conn.execute('INSERT INTO sync_configuracion(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))
