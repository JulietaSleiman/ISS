# Sincronización de sucursales y administración central

## Qué incorpora esta etapa

Cada computadora continúa operando con SQLite local, con un usuario responsable.
Los cambios locales de productos y existencias, las ventas y los cierres se
registran para envío a Supabase. Las operaciones pendientes sobreviven al cierre
de la aplicación. Los reintentos utilizan identificadores y revisiones para no
duplicar ventas ni reemplazar un estado nuevo por uno antiguo.

El catálogo y los precios son **por sucursal** en esta etapa. Dos productos con
el mismo código de barras en sucursales diferentes siguen siendo registros
distintos. No se combinan automáticamente sus existencias ni se publica un
catálogo único compartido.

La administración central consulta las últimas copias recibidas de productos,
stock, ventas y cierres. Los datos de una sucursal desconectada pueden estar
atrasados. Una recepción reciente no garantiza que toda su cola ya haya llegado;
revisar también las operaciones pendientes informadas por la sucursal.

## Preparación del proyecto Supabase

1. Conservar un respaldo de la base local antes de actualizar. No copiar una
   misma base ya vinculada a sucursal para crear otra instalación.
2. Completar los scripts y el acceso de la primera etapa, según
   `docs/INSTALACION_SIMOCA.md`.
3. Ejecutar `supabase/004_entidades_y_central.sql` en SQL Editor con una
   sesión administradora del panel. No desactivar RLS ni usar una clave secreta
   dentro del ejecutable para resolver permisos.
4. Crear en **Authentication → Users → Add user** una cuenta administradora
   independiente con correo técnico
   `administracion.estacion-de-simoca@usuarios.invalid`, contraseña elegida
   directamente en el panel y **Auto Confirm User** habilitado. No enviar la
   contraseña por chat ni usar invitación a ese correo técnico.
5. Ejecutar `supabase/005_asignar_administracion.sql` para asignar el perfil
   administrativo de esa nueva cuenta. `caja1` conserva su rol de cajero.
6. Revisar el script opcional `supabase/006_verificar_entidades.sql` para comprobar
   la configuración. No sustituye las pruebas de aceptación con datos de prueba.

Los scripts se deben ejecutar en orden antes de distribuir la versión nueva.
La clave publishable permite a la aplicación utilizar las operaciones autorizadas;
no crea tablas, funciones, usuarios ni permisos administrativos.

No se ejecutó un build ni se publicó un ejecutable en esta entrega. La versión
del código preparada para la siguiente distribución es 1.1.0. El esquema remoto,
las cuentas y la prueba de aceptación deben estar listos antes de publicar.

## Preparar una sucursal adicional

Se utiliza el mismo proyecto de Supabase, el mismo esquema central y el mismo
ejecutable en todas las computadoras. Cada instalación conserva su base local y
su identidad de sucursal. No configurar variables de entorno por computadora ni
compilar un ejecutable por local.

La administración debe preparar manualmente lo siguiente:

1. Ejecutar `supabase/007_codigos_sucursales.sql` después de los scripts anteriores.
   El código estable se guarda en `sucursales.codigo`; Estación de Simoca utiliza
   `estacion-de-simoca`.
2. Crear la nueva sucursal con UUID propio, nombre, código ASCII estable sin espacios
   y estado activo. No reutilizar la identidad de Simoca. Un ejemplo ficticio de
   código es `sucursal-ejemplo`; debe darse de alta antes de intentar vincularla.
3. Crear en **Authentication → Users → Add user** una cuenta propia con correo
   técnico `<usuario>.<codigo>@usuarios.invalid`, contraseña elegida fuera del chat
   y **Auto Confirm User** habilitado. Para ese ejemplo sería
   `caja1.sucursal-ejemplo@usuarios.invalid`. Asignar el perfil al UUID de esa
   sucursal, usuario `caja1`, rol `cajero` y estado activo. No reasignar cuentas que
   ya tienen operaciones históricas a otro local. La cuenta de Auth sin perfil
   asignado no habilita acceso; no usar invitación por correo.
4. Abrir el mismo ejecutable en una computadora nueva, con su propia base SQLite.
   La pantalla **Configurar esta computadora** tiene el código de sucursal vacío:
   ingresar código, usuario y contraseña y pulsar **Vincular e ingresar**.
   Esta primera vinculación REQUIERE internet: el servidor valida sucursal activa,
   perfil autorizado y coherencia con la base local antes de completar el acceso.
5. Verificar el nombre mostrado antes de cargar productos o abrir caja. Los próximos
   accesos muestran **Iniciar sesión**, nombre guardado y código de solo lectura;
   solo se ingresan usuario y contraseña. La identidad se guarda en metadatos de
   SQLite fuera del EXE y sobrevive a las actualizaciones.

Una instalación existente de Simoca conserva su identidad y su habilitación offline
previa. Una computadora nueva no hereda esa habilitación y no se asigna a Simoca
por omitir el código. Si la configuración local está dañada, resolver el error con
un respaldo: no se utiliza una sucursal predeterminada para continuar.

No copiar `database.sqlite` ni `auth_cache` de una computadora ya vinculada para dar
de alta otro local. Tampoco borrar la base, el caché o los metadatos para cambiar
la sucursal de una instalación. No hay un botón de restablecimiento de sucursal:
un traslado requiere respaldo y un procedimiento explícito que preserve historial,
identidad y operaciones pendientes.

La cuenta administradora también se vincula al local de su perfil. Su panel permite
consultar las otras sucursales por los permisos centrales. Un puesto administrativo
independiente se configura mediante este mismo primer acceso, con su cuenta y base
propias; no se copia la base operativa de una caja para montar una consulta remota.

## Uso de la administración central

Iniciar sesión con el usuario `administracion` y la contraseña elegida. El menú
**Administración central** aparece únicamente para una cuenta administradora.
Los permisos también se verifican en las consultas de Supabase; ocultar el botón
no es el mecanismo de seguridad de los datos.

El panel abre en **Resumen visual**, con indicadores y gráficos de ventas, medios
de pago, stock y arqueos. **Detalle de operaciones** conserva las tablas y las
solicitudes de precios. Consultar `docs/REPORTES_VISUALES.md` para interpretar
los indicadores. Después de los scripts anteriores, administración debe ejecutar
`supabase/008_reportes_visuales.sql` en el SQL Editor del mismo proyecto para
habilitar los agregados gráficos. Si falta ese paso, se mantienen totales y tablas
y aparece una indicación de configuración pendiente, no gráficos con ceros ficticios.

- **Sucursal:** elegir todas o un local específico.
- **Desde/Hasta:** filtran ventas, cierres y solicitudes; productos muestra su
  último estado recibido, no una reconstrucción histórica del stock.
- **Resumen:** los totales se calculan sobre todos los registros que corresponden
  a los filtros en el servidor, no sumando únicamente las filas de la página.
- **Productos y stock / Ventas / Cierres / Cambios de precios:** páginas de hasta
  100 registros, con botones Anterior y Siguiente.
- **Actualizar:** realiza una consulta nueva. El panel informa si falló y no
  presenta una consulta anterior como actualizada. No es una vista en tiempo real.

El panel requiere conexión a Supabase. La pantalla local de ventas sigue
funcionando sin internet conforme a la habilitación offline del usuario.
No hay edición remota directa de stock: sus movimientos se registran en la
computadora de cada sucursal.

## Cambios de precios enviados desde administración

1. En Productos y stock, seleccionar el producto de la sucursal deseada.
2. Pulsar **Solicitar cambio de precios**, ingresar contado y tarjeta y revisar
   sucursal, producto y montos antes de confirmar.
3. La solicitud queda **pendiente**. No se presenta como aplicada hasta que la
   computadora de destino la reciba, valide y confirme.
4. Si la sucursal está sin internet, podrá seguir vendiendo con sus precios
   locales. Recibirá la solicitud al sincronizar nuevamente.
5. Si el precio local cambió desde la revisión usada por administración, se
   informa **CONFLICTO**. Actualizar el panel, revisar el precio vigente y crear
   una solicitud nueva; no sobrescribir a ciegas el cambio local.

Una solicitud de precios no modifica existencias. Los acuses y resultados se
consultan en Cambios de precios. Reintentar el envío de una misma operación no
debe crear una venta, un movimiento ni una solicitud aplicada por duplicado.

## Primera carga y funcionamiento sin conexión

Los registros existentes se preparan para su primera carga sin inventar un
vendedor para ventas antiguas. Los cierres históricos sin identidad original
siguen bajo las reglas de regularización local documentadas en la primera etapa.
No se convierten automáticamente en cierres autenticados de `caja1`.

La sincronización se intenta al iniciar sesión, al realizar una venta, al cerrar
un turno y periódicamente. Las modificaciones de productos se envían en los
intentos periódicos. Las cargas iniciales grandes pueden necesitar varios lotes;
el indicador muestra las operaciones pendientes y no debe interpretarse como
una conexión permanente.

Conservar siempre la base local y sus respaldos. Si aparece un error de permisos
o de esquema, corregir la configuración remota y reintentar; no borrar la cola
ni crear ventas nuevas para sustituir las que todavía no llegaron.

## Prueba de aceptación en una copia separada

No realizar estos pasos sobre la base del negocio para crear operaciones ficticias.
Usar una instalación y sucursal de prueba autorizadas, separadas de producción.

1. Ejecutar los scripts, crear las cuentas e ingresar online con `caja1`.
2. Verificar que aparecen los productos existentes y su stock en la consulta
   central después de completar la primera carga. No debe cambiar el stock local.
3. Cortar internet. Registrar una venta de producto simple y una de promoción;
   verificar localmente el descuento correcto de cada producto componente.
4. Cambiar un precio local y registrar un cierre con efectivo contado distinto
   al esperado. Cerrar y volver a abrir la aplicación; las operaciones pendientes
   deben seguir guardadas.
5. Restaurar internet y esperar el envío. Comparar ventas, precios, existencias
   y cierre con la base de prueba local. Reintentar sincronización y comprobar
   que no aparecen ventas duplicadas ni retroceden las revisiones.
6. Ingresar con `administracion`, elegir sucursal y fechas y comparar los totales
   del servidor con las operaciones de prueba, aunque haya varias páginas.
7. Solicitar un precio para un producto. Con el destino desconectado, debe
   permanecer pendiente. Al reconectarlo, comprobar la aplicación y su acuse.
8. Repetir con una solicitud basada en una revisión antigua y un precio cambiado
   localmente: debe informar CONFLICTO y conservar el precio local.
9. Verificar que `caja1` no accede a administración ni puede asignarse ese rol,
   y que una cuenta de otra sucursal no puede escribir datos del local de prueba.

Las pruebas automatizadas se ejecutan con `python -m unittest discover -s tests -v`.
Utilizan bases temporales y red simulada. No sustituyen la comprobación del
esquema remoto y de la aplicación empaquetada sobre una instalación de prueba.
