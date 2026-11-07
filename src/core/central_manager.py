"""Administración central: agregados de servidor y comandos de precios auditables."""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import math
from uuid import UUID

from src.core.auth_manager import AuthManager
from src.core.supabase_client import AuthError, SupabaseError
from src.core import supabase_client


class CentralManager:
    KINDS = ('productos', 'ventas', 'cierres', 'comandos')

    @staticmethod
    def _token():
        if AuthManager.require_user().role != 'admin':
            raise AuthError('Esta función requiere una cuenta de administración central.')
        return AuthManager.ensure_auth_token()

    @staticmethod
    def _uuid(value):
        if value is None:
            return None
        try:
            return str(UUID(str(value)))
        except (ValueError, TypeError, AttributeError):
            raise ValueError('El identificador de sucursal o producto no es válido.') from None

    @staticmethod
    def _filters(branch_id, fecha_desde, fecha_hasta):
        try:
            start = date.fromisoformat(fecha_desde) if fecha_desde else None
            end = date.fromisoformat(fecha_hasta) if fecha_hasta else None
        except (ValueError, TypeError):
            raise ValueError('Las fechas deben tener formato AAAA-MM-DD.') from None
        if start and end and start > end:
            raise ValueError('La fecha inicial no puede ser posterior a la final.')
        if start and end and end.year-start.year+1>500:
            raise ValueError('Seleccione un período de hasta 500 años.')
        return {'p_sucursal_id': CentralManager._uuid(branch_id),
                'p_fecha_desde': start.isoformat() if start else None,
                'p_fecha_hasta': end.isoformat() if end else None}

    @staticmethod
    def fetch_dashboard(branch_id=None, fecha_desde=None, fecha_hasta=None):
        params = CentralManager._filters(branch_id, fecha_desde, fecha_hasta)
        token = CentralManager._token()
        result = supabase_client.request('POST', '/rest/v1/rpc/resumen_central', params, access_token=token)
        if not isinstance(result, dict) or not isinstance(result.get('branches'), list) or not isinstance(result.get('totals'), dict) or not result.get('fetched_at'):
            raise SupabaseError('La administración central devolvió un resumen incompleto.')
        if 'charts' in result:
            CentralManager._validate_charts(result['charts'])
        return result  # PostgreSQL calcula los totales, sin depender de páginas truncadas.

    @staticmethod
    def _validate_charts(charts):
        """Accept the previous RPC without charts; reject malformed new RPC data."""
        def invalid():
            raise SupabaseError('La administración central devolvió gráficos incompletos o no válidos. Revise la migración 008.')

        def count(value):
            if type(value) is not int or not 0<=value<=9223372036854775807:
                invalid()

        def amount(value):
            if type(value) not in (int,float) or value<0:
                invalid()
            try:
                finite=math.isfinite(value)
            except OverflowError:
                invalid()
            if not finite:
                invalid()

        if not isinstance(charts,dict):
            invalid()
        trend=charts.get('sales_trend')
        if not isinstance(trend,dict) or trend.get('granularity') not in ('day','week','month','year') or not isinstance(trend.get('points'),list) or len(trend['points'])>500:
            invalid()
        previous=None
        for point in trend['points']:
            if not isinstance(point,dict) or not isinstance(point.get('date'),str):
                invalid()
            try:
                current=date.fromisoformat(point['date'])
            except (ValueError,TypeError):
                invalid()
            if current.isoformat()!=point['date'] or (previous is not None and current<=previous):
                invalid()
            grain=trend['granularity']
            if (grain=='week' and current.weekday()!=0) or (grain in ('month','year') and current.day!=1) or (grain=='year' and current.month!=1):
                invalid()
            amount(point.get('total'));count(point.get('count'))
            previous=current
        methods=charts.get('payment_methods')
        if not isinstance(methods,list) or len(methods)>500:
            invalid()
        labels=set()
        for method in methods:
            if not isinstance(method,dict):
                invalid()
            label=method.get('label')
            if not isinstance(label,str) or not label.strip() or len(label)>500 or any(ord(character)<32 for character in label) or label in labels:
                invalid()
            labels.add(label)
            amount(method.get('total'));count(method.get('count'))
        cash=charts.get('cash_closures')
        stock=charts.get('stock_health')
        if not isinstance(cash,dict) or not isinstance(stock,dict):
            invalid()
        for key in ('balanced_count','shortage_count','surplus_count'):
            count(cash.get(key))
        for key in ('shortage_total','surplus_total'):
            amount(cash.get(key))
        for key in ('healthy_count','low_count','out_count'):
            count(stock.get(key))

    @staticmethod
    def fetch_page(kind, branch_id=None, fecha_desde=None, fecha_hasta=None, page=0, page_size=100):
        if kind not in CentralManager.KINDS or type(page) is not int or not 0 <= page <= 1000000 or type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError('El tipo de consulta o la paginación no son válidos.')
        params = CentralManager._filters(branch_id, fecha_desde, fecha_hasta)
        params.update(p_kind=kind, p_page=page, p_page_size=page_size)
        token = CentralManager._token()
        result = supabase_client.request('POST', '/rest/v1/rpc/pagina_central', params, access_token=token)
        if not isinstance(result, dict) or not isinstance(result.get('rows'), list) or type(result.get('has_more')) is not bool or len(result['rows']) > page_size:
            raise SupabaseError('La administración central devolvió una página incompleta.')
        rows = []
        for original in result['rows']:
            if not isinstance(original, dict):
                raise SupabaseError('La administración central devolvió un registro no válido.')
            row = dict(original.get('payload') or {})
            row.update(original)
            if kind == 'comandos':
                row['creado_en'] = row.get('created_at')
                row['detalle'] = row.get('detail')
            rows.append(row)
        return {'rows': rows, 'has_more': result['has_more']}

    @staticmethod
    def _price(value):
        try:
            price = Decimal(str(value))
            if not price.is_finite() or price < 0 or price >= Decimal('100000000000000'):
                raise ValueError
            price = price.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            if price >= Decimal('100000000000000'):
                raise ValueError
            return float(price)
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError('Ingrese precios finitos, mayores o iguales a cero y dentro del rango permitido.') from None

    @staticmethod
    def request_price_change(branch_id, product_id, expected_catalog_revision, precio_contado, precio_tarjeta):
        branch_id = CentralManager._uuid(branch_id)
        product_id = CentralManager._uuid(product_id)
        if not branch_id or not product_id or type(expected_catalog_revision) is not int or expected_catalog_revision <= 0:
            raise ValueError('Seleccione un producto y su revisión actual de catálogo.')
        params = {'p_sucursal_id': branch_id, 'p_producto_id': product_id,
                  'p_expected_catalog_revision': expected_catalog_revision,
                  'p_precio_contado': CentralManager._price(precio_contado),
                  'p_precio_tarjeta': CentralManager._price(precio_tarjeta)}
        token = CentralManager._token()
        try:
            result = supabase_client.request('POST', '/rest/v1/rpc/solicitar_cambio_precios', params, access_token=token)
        except SupabaseError:
            raise SupabaseError('No se pudo registrar la solicitud. Actualice el catálogo y revise si ya hay un cambio pendiente o si perdió permisos.') from None
        if not isinstance(result, dict) or not result.get('id') or result.get('estado') != 'PENDIENTE':
            raise SupabaseError('No se recibió una confirmación válida de la solicitud de precios.')
        return result
