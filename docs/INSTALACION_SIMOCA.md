# Primera instalación: Estación de Simoca

La primera etapa incorpora acceso de operadores, responsabilidad de apertura y
cierre, arqueo de efectivo contado y envío de cierres a Supabase. La etapa
siguiente agrega productos, ventas, existencias por sucursal y administración
central; requiere los pasos adicionales de `docs/SINCRONIZACION_SUCURSALES.md`.
SQLite continúa siendo la base operativa local. Las cuentas corrientes no tienen
un módulo de administración central en esta entrega.

## 1. Preparar la computadora

1. Conservar una copia de `database.sqlite` y sus respaldos antes de actualizar.
   Si hay una caja de una versión anterior todavía abierta, seguir el
   procedimiento de cierre histórico que se describe a continuación. La
   aplicación no atribuye automáticamente su apertura a `caja1`.
2. Conservar la base local. En el ejecutable se encuentra normalmente en
   `C:\SistemaIvanLlorens\database.sqlite`; si Windows no permite esa ubicación,
   la aplicación utiliza `%LOCALAPPDATA%\SistemaIvanLlorens`.
3. Para ejecutar desde código, instalar Python y las dependencias de
   `requirements.txt` en un entorno virtual. Desde la raíz del proyecto:

   ```powershell
   python -m pip install -r requirements.txt
   ```

No se compiló un ejecutable nuevo en esta entrega. No reemplazar el programa de
producción hasta completar la configuración y la prueba de aceptación.

### Si aparece una caja anterior sin responsable

En **Caja Diaria** se muestra una tarjeta de revisión con el botón
**Cerrar caja anterior**. Esta operación es explícita y no se ejecuta al iniciar:

1. Seleccionar el turno por su número y fecha de apertura.
2. Ingresar el efectivo realmente contado, sin copiar automáticamente el esperado.
3. Escribir un motivo de al menos 10 caracteres.
4. Revisar esperado, contado, diferencia y el usuario que regulariza; confirmar
   únicamente si los datos son correctos.

Antes de modificar el turno se crea un respaldo consistente de SQLite. La
confirmación informa dónde quedó guardado. Se conserva el responsable de apertura
como **No registrado (versión anterior)** y se audita quién realizó el cierre,
con su motivo. No se inventa una sucursal de origen ni se envía ese historial
antiguo a Supabase. Si hay más cajas anteriores, se revisan individualmente.
Al terminar se habilita la apertura del primer turno nuevo con responsable.

El botón solo corresponde a registros realmente anteriores, sin identidad
asignada. No permite cerrar un turno perteneciente a otra persona ni reparar
automáticamente metadatos incompletos. Ante otro error, conservar el respaldo y
revisar el registro antes de operar.

## 2. Crear el esquema de Supabase

En el proyecto `zhodbzfqkezwjtvktyit`, abrir **SQL Editor**, crear una consulta,
copiar el contenido completo de `supabase/001_sucursales_caja.sql` y ejecutarlo.
Esto requiere una sesión administradora del panel, no la clave pública del programa.

El script configura las tablas, los permisos y Estación de Simoca. Ejecutar también
`supabase/007_codigos_sucursales.sql` para habilitar los códigos estables de sucursal
(`sucursales.codigo`); para Simoca el código es `estacion-de-simoca`. No conceder
acceso anónimo ni desactivar RLS para solucionar errores de configuración.

## 3. Crear la cuenta caja1

En **Authentication → Users → Add user**, crear manualmente esta cuenta:

- Correo técnico: `caja1.estacion-de-simoca@usuarios.invalid`.
- Contraseña: elegirla e ingresarla directamente en el panel. No guardarla en
  archivos del proyecto ni enviarla por chat.
- Confirmar automáticamente el correo (**Auto Confirm User**), ya que se trata de
  un identificador técnico que no recibe mensajes.

No usar invitación por correo para esta cuenta. En la configuración de
**Authentication**, buscar **Allow new users to sign up**, verificar su estado y
deshabilitar el registro público de nuevos usuarios. Este correo no se escribe en la pantalla de
acceso: el operador utiliza `caja1` y su contraseña. Si olvida la contraseña, la
administración debe restablecerla desde el panel; no hay recuperación por correo
para este identificador técnico.

Después ejecutar en SQL Editor `supabase/002_asignar_caja1.sql`. Este paso asigna
la cuenta de Auth a la sucursal y al rol de cajero. Crear la cuenta de Auth sin
asignar el perfil NO habilita el acceso.

La URL y la clave publishable del proyecto están en `src/core/app_config.py`.
Son configuración pública del cliente; nunca reemplazarlas por `service_role`,
una clave secreta o la contraseña de PostgreSQL.

## 4. Primer acceso y uso sin conexión

1. Con internet disponible, ejecutar desde la raíz:

   ```powershell
   python main.py
   ```

2. En una computadora nueva aparece **Configurar esta computadora**, sin sucursal
   preseleccionada. Ingresar código `estacion-de-simoca`, usuario `caja1` y la
   contraseña configurada en el panel; pulsar **Vincular e ingresar**. El servidor
   debe confirmar código activo, perfil y sucursal antes de vincular la instalación.
3. Comprobar la sucursal y el usuario que aparecen en el menú. En los próximos
   accesos aparece **Iniciar sesión**, con el nombre guardado y código de sucursal
   de solo lectura. La instalación anterior de Simoca conserva su identidad y
   acceso offline previamente habilitado; no requiere reasignación automática.
4. El primer acceso correcto habilita el acceso local de esa persona en esa
   computadora y cuenta de Windows. El caché está protegido por DPAPI; no se
   guarda la contraseña en texto plano.
5. Sin internet, puede ingresar con las mismas credenciales previamente
   verificadas durante 30 días desde la última autenticación válida online.
   Volver a ingresar con conexión renueva esa habilitación. No hay un usuario
   predeterminado ni una contraseña de emergencia que evite la autenticación.

Se distribuye el mismo ejecutable para todas las sucursales. No se necesitan
variables de entorno por computadora ni un ejecutable diferente por local.
La identidad de instalación se guarda en metadatos de SQLite fuera del ejecutable
y sobrevive a sus actualizaciones. Una computadora nueva necesita internet para
la primera vinculación; el modo offline corresponde a accesos ya verificados.
No borrar la base ni el caché para cambiar de sucursal: un traslado requiere
respaldo y un procedimiento explícito que preserve identidad, historial y cola.

Si aparece una advertencia de que no se pudo habilitar el acceso sin conexión,
resolverla antes de retirar internet de la computadora. DPAPI vincula el caché
a la cuenta de Windows: copiarlo a otra computadora o cuenta no habilita acceso.

La desactivación central de un usuario no puede conocerse mientras el equipo
está desconectado. Al recibir un rechazo explícito del servidor se invalida la
habilitación y se bloquea la sesión. El plazo offline limita esa demora, pero no
sustituye la protección física de la computadora y sus respaldos.

## 5. Prueba de aceptación antes de usar datos reales

Hacerla con una copia de prueba, separada de la base del negocio:

1. Iniciar sesión online y abrir un turno como `caja1` con $1.000.
2. Registrar las operaciones de prueba y comprobar el efectivo esperado.
3. Cerrar el turno ingresando el efectivo realmente contado. Por ejemplo, sin
   movimientos, declarar $990 debe registrar esperado $1.000 y diferencia -$10.
4. Verificar responsable de apertura, usuario de cierre, contado y diferencia en
   **Reportes → Caja**.
5. Verificar en Supabase que existe una fila en `cierres_caja` para ese cierre.
6. Repetir sin internet: el cierre debe guardarse localmente y quedar pendiente.
7. Restaurar internet y esperar el reintento (cada minuto). El cierre debe llegar
   una sola vez aunque se reintente el envío. El indicador informa pendientes o
   errores; no eliminar la base local para resolver un error de sincronización.
8. Cerrar y volver a abrir la aplicación sin internet con `caja1`; verificar que
   el acceso previamente habilitado funciona.

En esta primera etapa cada usuario envía sus propios cierres pendientes. Si se
cambia de usuario antes de enviarlos, volver a ingresar con la cuenta original y
conexión disponible para completar el envío. No borrar ni reasignar la cola.

Cada persona debe tener una cuenta propia cuando se incorporen más operadores.
Una cuenta compartida identifica la cuenta responsable, no permite distinguir
qué persona física hizo cada operación.

En esta etapa cada perfil pertenece a una sucursal. No reasignar una cuenta con
cierres históricos a otra sucursal: crear una cuenta nueva para ese destino y
conservar la identidad original del historial.

## Validación del código

```powershell
python -m unittest discover -s tests -v
```

Las pruebas usan bases temporales y simulaciones de red. No crean usuarios ni
tablas en Supabase y no prueban una actualización real del ejecutable. Los pasos
del panel y la aceptación online/offline deben completarse antes de instalar.
