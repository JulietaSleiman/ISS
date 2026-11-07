-- Consultas de solo lectura para verificar la etapa 2; no prueban por sí solas la sincronización.
SELECT table_name FROM information_schema.tables WHERE table_schema='public'
    AND table_name IN ('productos_sucursal','ventas_sucursal','sucursales_estado','sync_eventos_recibidos','comandos_precios');
SELECT c.relname,c.relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname IN ('productos_sucursal','ventas_sucursal','sucursales_estado','sync_eventos_recibidos','comandos_precios');
SELECT rol,username,sucursal_id,activo FROM public.profiles WHERE username IN ('caja1','administracion');
SELECT r.rolname,p.proname,has_function_privilege(r.rolname,p.oid,'EXECUTE') AS puede_ejecutar
    FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
    CROSS JOIN pg_roles r WHERE n.nspname='public' AND p.proname IN
    ('sincronizar_entidades','solicitar_cambio_precios','confirmar_comandos_precios','resumen_central','pagina_central')
    AND r.rolname IN ('anon','authenticated');
SELECT tablename,policyname,cmd FROM pg_policies WHERE schemaname='public' AND tablename IN
    ('productos_sucursal','ventas_sucursal','sucursales_estado','comandos_precios');
SELECT id,nombre,e.last_sync_at FROM public.sucursales s LEFT JOIN public.sucursales_estado e ON e.sucursal_id=s.id;
SELECT count(*) AS eventos_recibidos FROM public.sync_eventos_recibidos;
SELECT estado,count(*) FROM public.comandos_precios GROUP BY estado;

-- Después de aplicar 007, comprobar también códigos sin fallar si aún no existe
-- la columna (006 sigue siendo utilizable durante el despliegue de la etapa 2).
SELECT s.id,s.nombre,to_jsonb(s)->>'codigo' AS codigo FROM public.sucursales s;
