import sqlite3
import uuid
from unittest.mock import patch
import unittest

from src.core.auth_manager import AuthManager
from src.core.entity_sync_store import EntitySyncStore
from src.core.productos_manager import ProductosManager
from test_entity_sync import EntitySyncCase


class PriceCommandTests(EntitySyncCase):
    def command(self, product_id, **changes):
        product = ProductosManager.get_by_id(product_id)
        result = dict(id=str(uuid.uuid4()), sucursal_id=self.user.branch_id,
            producto_id=product['sync_id'], expected_catalog_revision=product['catalog_revision'],
            precio_contado=30, precio_tarjeta=35)
        result.update(changes)
        return result

    def test_stock_change_does_not_conflict_and_central_prices_never_overwrite_stock(self):
        product_id = self.product()
        command = self.command(product_id)
        ProductosManager.actualizar_stock(product_id, -4)
        result = EntitySyncStore.apply_price_command(command, self.user)
        self.assertEqual(result['status'], 'APLICADO')
        product = ProductosManager.get_by_id(product_id)
        self.assertEqual((product['stock_actual'], product['precio_contado'], product['precio_tarjeta']), (16, 30, 35))
        self.assertEqual((product['sync_revision'], product['catalog_revision']), (3, 2))
        self.assertEqual(self.events()[-1]['payload']['stock_actual'], 16)
        self.assertEqual(self.sql('SELECT estado, ack_en FROM sync_comandos_aplicados'), [{'estado': 'APLICADO', 'ack_en': None}])

    def test_offline_catalog_edit_creates_durable_conflict_without_overwriting(self):
        product_id = self.product()
        command = self.command(product_id)
        self.edit(product_id, nombre='Nombre cambiado sin internet')
        before = dict(ProductosManager.get_by_id(product_id))
        count = len(self.events())
        result = EntitySyncStore.apply_price_command(command, self.user)
        self.assertEqual(result['status'], 'CONFLICTO')
        self.assertEqual(dict(ProductosManager.get_by_id(product_id)), before)
        self.assertEqual(len(self.events()), count)
        self.assertEqual(self.sql('SELECT estado FROM sync_comandos_aplicados')[0]['estado'], 'CONFLICTO')

    def test_duplicate_command_returns_original_receipt_without_reapplying_prices(self):
        product_id = self.product()
        command = self.command(product_id)
        first = EntitySyncStore.apply_price_command(command, self.user)
        self.edit(product_id, precio_contado=99)
        before = dict(ProductosManager.get_by_id(product_id))
        event_count = len(self.events())
        duplicate = EntitySyncStore.apply_price_command(command, self.user)
        self.assertEqual(duplicate, first)
        self.assertEqual(dict(ProductosManager.get_by_id(product_id)), before)
        self.assertEqual(len(self.events()), event_count)
        self.assertEqual(len(self.sql('SELECT * FROM sync_comandos_aplicados')), 1)

    def test_missing_product_result_is_durable_and_not_reinterpreted_on_retry(self):
        product_id = self.product()
        command = self.command(product_id, producto_id=str(uuid.uuid4()))
        first = EntitySyncStore.apply_price_command(command, self.user)
        self.assertEqual(first['status'], 'NO_ENCONTRADO')
        self.sql('UPDATE productos SET sync_id=? WHERE id=?', (command['producto_id'], product_id))
        self.assertEqual(EntitySyncStore.apply_price_command(command, self.user), first)
        self.assertEqual(ProductosManager.get_by_id(product_id)['precio_contado'], 20)

    def test_receipt_storage_failure_rolls_back_prices_revisions_and_outbox(self):
        product_id = self.product()
        command = self.command(product_id)
        before = dict(ProductosManager.get_by_id(product_id))
        self.sql("CREATE TRIGGER fail_command BEFORE INSERT ON sync_comandos_aplicados BEGIN SELECT RAISE(ABORT, 'receipt storage failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            EntitySyncStore.apply_price_command(command, self.user)
        self.assertEqual(dict(ProductosManager.get_by_id(product_id)), before)
        self.assertEqual(len(self.events()), 1)
        self.assertEqual(self.sql('SELECT * FROM sync_comandos_aplicados'), [])

    def test_wrong_branch_invalid_price_or_revision_is_not_applied_or_acknowledged(self):
        product_id = self.product()
        for changes in (
            {'sucursal_id': str(uuid.uuid4())}, {'precio_contado': -1},
            {'precio_tarjeta': float('nan')}, {'precio_tarjeta': float('inf')},
            {'expected_catalog_revision': True}, {'expected_catalog_revision': 1.5},
            {'expected_catalog_revision': 0}, {'precio_contado': 100_000_000_000_000},
        ):
            with self.assertRaises(ValueError):
                EntitySyncStore.apply_price_command(self.command(product_id, **changes), self.user)
        self.assertEqual(ProductosManager.get_by_id(product_id)['precio_contado'], 20)
        self.assertEqual(self.sql('SELECT * FROM sync_comandos_aplicados'), [])

    def test_command_requires_current_authenticated_user(self):
        product_id = self.product()
        with patch.object(AuthManager, 'require_user', side_effect=RuntimeError('Debe iniciar sesión')):
            with self.assertRaises(RuntimeError):
                EntitySyncStore.apply_price_command(self.command(product_id), self.user)
        self.assertEqual(self.sql('SELECT * FROM sync_comandos_aplicados'), [])


if __name__ == '__main__':
    unittest.main()
