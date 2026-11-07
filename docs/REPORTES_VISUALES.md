# Resumen visual del negocio

La administración central abre en **Resumen visual**. Primero elegir una sucursal
o todas, el período y **Actualizar**. Los accesos **Hoy**, **7 días**, **Este mes**
y **30 días** cambian las fechas y realizan una consulta. El período incluye ambos
extremos; siete días comprende hoy y los seis días anteriores.

## Qué responde cada indicador

- **Ventas del período:** importe de ventas recibidas; no representa cobros ni ganancias.
- **Operaciones:** cantidad de ventas del período recibidas por el servidor.
- **Ticket promedio:** ventas divididas por operaciones. Sin operaciones se muestra
  un guion, no un promedio inventado.
- **Productos con stock bajo:** productos que requieren atención según el último
  estado recibido de cada sucursal. Es estado actual y no lo filtran las fechas.
- **Cajas con diferencia:** cantidad de cierres con faltante o sobrante del período.
- **Pendientes informados:** suma de los últimos reportes conocidos. Se informa
  cuántas sucursales no enviaron ese dato; no se interpreta su ausencia como cero.

## Cómo leer los gráficos

- **Evolución de ventas:** muestra el importe vendido por fecha. Para períodos
  extensos el servidor agrupa por semana, mes o año; no se construye a partir de
  la página de ventas visible.
- **Ventas por sucursal:** compara la participación en los importes vendidos.
  Pulsar una sucursal aplica ese filtro y actualiza conservando las fechas.
- **Medios de pago:** distribuye importes de ventas según el medio registrado.
  **MIXTO** conserva su categoría: no pretende desglosar efectivo y transferencia.
- **Alertas de stock por sucursal:** compara cantidades de productos con alertas
  en el último estado recibido. Pulsar un local permite consultar sus detalles;
  la tabla de productos no queda filtrada exclusivamente a alertas.
- **Arqueos de caja:** cuenta cierres sin diferencia, con faltante y con sobrante.
  Los importes de faltantes y sobrantes se muestran separados y no se compensan.

Los botones **Ver detalle** llevan a **Detalle de operaciones**, donde siguen
disponibles las tablas de productos, ventas, cierres y cambios de precios, con
paginación y solicitudes de precios. **Ver estado de sucursales** permite revisar
última recepción y pendientes por local.

## Vigencia y datos faltantes

La fecha de consulta indica cuándo se recibió la respuesta del servidor; no
garantiza que un local desconectado haya enviado toda su información. Los gráficos,
tarjetas y tablas corresponden a datos recibidos, no a una conexión en tiempo real.
Al cambiar filtros o consultar nuevamente, los indicadores anteriores quedan
marcados como **Datos anteriores**. Un error conserva esos datos como referencia,
sin presentarlos como actualizados ni permitir solicitar precios con esa consulta.

Sin importes distribuibles o cierres, los gráficos lo indican explícitamente.
Una venta gratuita sigue siendo una operación; no se confunde importe cero con
ausencia de ventas. Sin inventario recibido tampoco se afirma que no hay alertas.
Si falta configuración de los gráficos se muestra **Actualizar configuración de
reportes**; eso no significa que el negocio tenga ventas iguales a cero.

## Preparación administrativa

Después de los scripts anteriores, ejecutar manualmente
`supabase/008_reportes_visuales.sql` en el SQL Editor del mismo proyecto de Supabase,
con una sesión administradora. Conserva los permisos de administración y agrega
los agregados completos para los gráficos. La aplicación no ejecuta este script
ni requiere claves secretas en el ejecutable. No desactivar RLS.

Comprobar con una sucursal de prueba ventas simples, ventas mixtas, un cierre con
faltante y otro con sobrante. Comparar totales con las operaciones completas,
incluyendo más de una página cuando corresponda. Revisar también un período sin
operaciones y el cambio de filtros sin conexión. La revisión automatizada usa
datos simulados; no sustituye esa aceptación contra el esquema remoto.
