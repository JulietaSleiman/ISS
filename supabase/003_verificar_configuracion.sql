-- Solo lectura: ejecutar tras 001, crear el usuario y ejecutar 002.
-- Esperado: tres tablas con RLS = true.
SELECT schemaname, tablename, rowsecurity AS rls
FROM pg_tables WHERE schemaname = 'public'
AND tablename IN ('sucursales', 'profiles', 'cierres_caja');

-- Esperado: authenticated SELECT en las tres e INSERT solo en cierres_caja.
-- NO deben existir privilegios para anon, ni UPDATE/DELETE para authenticated.
SELECT grantee, table_name, privilege_type
FROM information_schema.role_table_grants
WHERE table_schema = 'public'
AND table_name IN ('sucursales', 'profiles', 'cierres_caja')
AND grantee IN ('anon', 'authenticated', 'PUBLIC')
ORDER BY grantee, table_name, privilege_type;

-- Esperado: políticas SELECT y una INSERT en cierres; ninguna ALL/UPDATE/DELETE.
SELECT tablename, policyname, roles, cmd, qual, with_check
FROM pg_policies WHERE schemaname = 'public'
AND tablename IN ('sucursales', 'profiles', 'cierres_caja');

-- Esperado: caja1 asignado a Estación de Simoca y rol cajero activo.
SELECT p.username, p.rol, p.activo, s.nombre AS sucursal, s.activa
FROM public.profiles p JOIN public.sucursales s ON s.id = p.sucursal_id
WHERE p.username = 'caja1';

-- Esta consulta no valida RLS funcionalmente: SQL Editor usa un rol privilegiado.
-- Completar prueba desde la app con caja1: cierre, reintento sin duplicar,
-- y comprobar que una petición sin sesión no puede consultar ni insertar cierres.
