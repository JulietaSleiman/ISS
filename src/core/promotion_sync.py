"""Intercambio de promociones por sucursal sin usar IDs locales de productos."""
from contextlib import closing
from urllib.parse import urlencode

from src.core import supabase_client
from src.core.entity_sync_store import EntitySyncStore
from src.db.database import get_connection


def sync_promotions(user, token, result):
    with closing(get_connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        EntitySyncStore._bind(conn, user)
        pending = []
        for promo in conn.execute('SELECT * FROM promociones WHERE sync_pending=1 ORDER BY id LIMIT 50'):
            identity = EntitySyncStore._uuid(conn, 'promociones', promo['id'])
            details = conn.execute("""
                SELECT p.sync_id AS producto, d.cantidad_requerida
                FROM promocion_detalles d JOIN productos p ON p.id=d.producto_id
                WHERE d.promocion_id=? ORDER BY d.id
            """, (promo['id'],)).fetchall()
            if any(not detail['producto'] for detail in details):
                continue
            pending.append((identity, promo['sync_revision'], {
                'nombre': promo['nombre'], 'precio_fijo': promo['precio_fijo'],
                'activa': bool(promo['activa']), 'detalles': [dict(detail) for detail in details],
            }))

    conflicts = []
    for identity, revision, payload in pending:
        confirmed = supabase_client.request('POST', '/rest/v1/rpc/guardar_promocion_sucursal', {
            'p_sucursal': user.branch_id, 'p_id': identity, 'p_revision': revision, 'p_payload': payload,
        }, access_token=token)
        if confirmed is not True:
            conflicts.append(payload['nombre'])
            continue
        with closing(get_connection()) as conn, conn:
            conn.execute('UPDATE promociones SET sync_pending=0 WHERE sync_id=? AND sync_revision=?',
                         (identity, revision))

    cursor = None
    while True:
        filters = {'sucursal_id': f'eq.{user.branch_id}', 'order': 'id.asc', 'limit': 50}
        if cursor:
            filters['id'] = f'gt.{cursor}'
        rows = supabase_client.request('GET', '/rest/v1/promociones_sucursal?' + urlencode(filters),
                                       access_token=token)
        if not isinstance(rows, list):
            raise ValueError('La lista de promociones recibida no es válida.')
        if not rows:
            break
        for row in rows:
            if row['sucursal_id'] != user.branch_id or (cursor and row['id'] <= cursor):
                raise ValueError('Se recibió una promoción de otra sucursal o fuera de orden.')
            cursor = row['id']
            if apply_promotion(user, row):
                result['promotions_changed'] = True
    if conflicts:
        raise ValueError('Promociones con cambios en conflicto: ' + ', '.join(conflicts))


def apply_promotion(user, row):
    with closing(get_connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        EntitySyncStore._bind(conn, user)
        local = conn.execute('SELECT * FROM promociones WHERE sync_id=?', (row['id'],)).fetchone()
        if local and (local['sync_pending'] or local['sync_revision'] >= row['revision']):
            return False
        payload = row['payload']
        details = []
        for detail in payload['detalles']:
            product = conn.execute('SELECT id FROM productos WHERE sync_id=?',
                                   (detail['producto'],)).fetchone()
            if product is None:
                return False  # Se reintenta cuando llegue el producto.
            details.append((product['id'], detail['cantidad_requerida']))
        values = (payload['nombre'], payload['precio_fijo'], int(payload['activa']), row['revision'])
        if local:
            local_id = local['id']
            conn.execute('UPDATE promociones SET nombre=?, precio_fijo=?, activa=?, sync_revision=? WHERE id=?',
                         (*values, local_id))
            conn.execute('DELETE FROM promocion_detalles WHERE promocion_id=?', (local_id,))
        else:
            local_id = conn.execute("""
                INSERT INTO promociones(nombre,precio_fijo,activa,sync_revision,sync_id,sync_pending)
                VALUES (?,?,?,?,?,0)
            """, (*values, row['id'])).lastrowid
        conn.executemany("""
            INSERT INTO promocion_detalles(promocion_id,producto_id,cantidad_requerida) VALUES (?,?,?)
        """, ((local_id, product_id, quantity) for product_id, quantity in details))
        return True
