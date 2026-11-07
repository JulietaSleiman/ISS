-- PRUEBA MANUAL: proyecto DE PRUEBAS con 001,004,008. No ejecutada por Codex.
-- Crea fixtures aislados y revierte TODO. No ejecutar sobre producción.
BEGIN;
DO $$
DECLARE branch uuid:=gen_random_uuid(); other_branch uuid:=gen_random_uuid();
        admin_id uuid:=gen_random_uuid(); cashier uuid:=gen_random_uuid(); foreign_user uuid:=gen_random_uuid();
BEGIN
    INSERT INTO public.sucursales(id,nombre) VALUES(branch,'Reportes de prueba'),(other_branch,'Otra sucursal de prueba');
    INSERT INTO auth.users(id,email,aud,role,email_confirmed_at) VALUES
        (admin_id,admin_id::text||'@usuarios.invalid','authenticated','authenticated',now()),
        (cashier,cashier::text||'@usuarios.invalid','authenticated','authenticated',now()),
        (foreign_user,foreign_user::text||'@usuarios.invalid','authenticated','authenticated',now());
    INSERT INTO public.profiles(id,username,sucursal_id,nombre,rol) VALUES
        (admin_id,'adminprueba',branch,'Administrador de prueba','admin'),
        (cashier,'cajaprueba',branch,'Caja de prueba','cajero'),
        (foreign_user,'otraprueba',other_branch,'Otra caja de prueba','cajero');
    INSERT INTO public.productos_sucursal(sucursal_id,id,revision,catalog_revision,local_id,nombre,
        precio_contado,precio_tarjeta,stock_actual,stock_minimo,activo,payload,synced_at)
        SELECT branch,gen_random_uuid(),1,1,p.local_id,'Producto de prueba',10,12,p.stock,5,p.activo,
            '{}'::jsonb,'2020-01-01T00:00:00Z'::timestamptz
        FROM (VALUES(1,10,true),(2,2,true),(3,0,true),(4,-2,true),(5,999,false)) p(local_id,stock,activo);
    INSERT INTO public.ventas_sucursal(sucursal_id,id,revision,local_id,fecha,subtotal,descuento_total,total,
        metodo_pago,estado,vendedor_id,historica,payload) VALUES
        (branch,gen_random_uuid(),1,1,'2026-11-01T03:00:00Z',100,0,100,'EFECTIVO','COMPLETADA',cashier,false,'{"detalles":[]}'),
        (branch,gen_random_uuid(),1,2,'2026-11-04T02:59:59Z',50,0,50,'MIXTO','COMPLETADA',cashier,false,'{"detalles":[]}'),
        (branch,gen_random_uuid(),1,3,'2026-11-02T12:00:00Z',999,0,999,'EFECTIVO','CANCELADA',cashier,false,'{"detalles":[]}'),
        (branch,gen_random_uuid(),1,4,'2026-11-04T03:00:00Z',100,0,100,'EFECTIVO','COMPLETADA',cashier,false,'{"detalles":[]}'),
        (other_branch,gen_random_uuid(),1,1,'2026-11-02T12:00:00Z',1000,0,1000,'TRANSFERENCIA','COMPLETADA',foreign_user,false,'{"detalles":[]}');
    INSERT INTO public.cierres_caja(id,sucursal_id,responsable_id,responsable_nombre,cierre_usuario_id,
        cierre_usuario_nombre,fecha_apertura,fecha_cierre,monto_inicial,monto_esperado,monto_cierre,diferencia,resumen)
        SELECT gen_random_uuid(),branch,cashier,'Caja',cashier,'Caja',
            ('2026-11-0'||c.day::text||'T03:00:00Z')::timestamptz,
            ('2026-11-0'||c.day::text||'T04:00:00Z')::timestamptz,100,100,100+c.diff,c.diff,'{}'::jsonb
        FROM(VALUES(1,0),(2,-20),(3,20))c(day,diff);
    PERFORM set_config('iss_visual.branch',branch::text,true);
    PERFORM set_config('iss_visual.other_branch',other_branch::text,true);
    PERFORM set_config('iss_visual.admin',admin_id::text,true);
    PERFORM set_config('iss_visual.cashier',cashier::text,true);
END;
$$;

SET LOCAL ROLE anon;
DO $$
DECLARE rejected boolean:=false;
BEGIN
    BEGIN PERFORM public.resumen_central();
    EXCEPTION WHEN insufficient_privilege THEN rejected:=true; END;
    ASSERT rejected,'anon no puede ejecutar el resumen';
END;
$$;
RESET ROLE;
SELECT set_config('request.jwt.claim.sub',current_setting('iss_visual.cashier'),true);
SET LOCAL ROLE authenticated;
DO $$
DECLARE rejected boolean:=false;
BEGIN
    BEGIN PERFORM public.resumen_central();
    EXCEPTION WHEN insufficient_privilege THEN rejected:=true; END;
    ASSERT rejected,'Un cajero no puede consultar reportes centrales';
END;
$$;
RESET ROLE;
SELECT set_config('request.jwt.claim.sub',current_setting('iss_visual.admin'),true);
SET LOCAL ROLE authenticated;
DO $$
DECLARE report jsonb; charts jsonb; points jsonb; mixed jsonb; amount numeric; report_count bigint;
        rejected boolean:=false;
BEGIN
    report:=public.resumen_central(current_setting('iss_visual.branch')::uuid,'2026-11-01','2026-11-03');
    charts:=report->'charts';points:=charts->'sales_trend'->'points';
    ASSERT (report->'totals'->>'total_vendido')::numeric=150,'Debe excluir canceladas, otra sucursal y límite exclusivo';
    ASSERT (report->'totals'->>'ventas_count')::integer=2,'Conteo de ventas incorrecto';
    ASSERT charts->'sales_trend'->>'granularity'='day' AND jsonb_array_length(points)=3,'Serie diaria incorrecta';
    ASSERT points->1->>'date'='2026-11-02' AND (points->1->>'count')::integer=0,'Debe rellenar días sin ventas';
    ASSERT (points->2->>'total')::numeric=50,'No debe perder el último día o bucket incompleto';
    SELECT sum((p->>'total')::numeric),sum((p->>'count')::bigint) INTO amount,report_count FROM jsonb_array_elements(points) AS a(p);
    ASSERT amount=150 AND report_count=2,'Serie y totales deben cubrir exactamente el mismo conjunto';
    SELECT p INTO mixed FROM jsonb_array_elements(charts->'payment_methods') AS a(p) WHERE p->>'label'='Mixto';
    ASSERT (mixed->>'total')::numeric=50 AND (mixed->>'count')::integer=1,'Mixto no se desglosa ni se trata como cobro';
    ASSERT (charts->'cash_closures'->>'balanced_count')::integer=1,'Diferencias compensadas no equivalen a cajas cuadradas';
    ASSERT (charts->'cash_closures'->>'shortage_count')::integer=1 AND
        (charts->'cash_closures'->>'surplus_count')::integer=1,'Debe separar faltantes y sobrantes';
    ASSERT (charts->'cash_closures'->>'shortage_total')::numeric=20 AND
        (charts->'cash_closures'->>'surplus_total')::numeric=20,'No debe compensar importes de caja';
    ASSERT (charts->'stock_health'->>'healthy_count')::integer=1 AND
        (charts->'stock_health'->>'low_count')::integer=1 AND
        (charts->'stock_health'->>'out_count')::integer=2,'Stock activo debe dividirse en tres grupos excluyentes';
    ASSERT (report->'totals'->>'productos_count')::integer=4,'Inventario vigente no depende de fecha synced_at';
    report:=public.resumen_central(current_setting('iss_visual.other_branch')::uuid,'2026-11-01','2026-11-03');
    ASSERT (report->'totals'->>'total_vendido')::numeric=1000,'Filtro de sucursal debe afectar todos los gráficos';
    ASSERT (report->'charts'->'cash_closures'->>'balanced_count')::integer=0,'No debe mezclar cierres de otra sucursal';
    report:=public.resumen_central(current_setting('iss_visual.branch')::uuid,'2026-01-01','2026-12-31');
    ASSERT report->'charts'->'sales_trend'->>'granularity'='week','Rango anual debe agrupar por semana';
    report:=public.resumen_central(current_setting('iss_visual.branch')::uuid,'2020-01-01','2026-12-31');
    ASSERT report->'charts'->'sales_trend'->>'granularity'='month','Rango de siete años debe agrupar por mes';
    report:=public.resumen_central(current_setting('iss_visual.branch')::uuid,'2000-01-01','2026-12-31');
    ASSERT report->'charts'->'sales_trend'->>'granularity'='year','Rango largo debe agrupar por año';
    BEGIN PERFORM public.resumen_central(NULL,'0001-01-01','9999-12-31');
    EXCEPTION WHEN others THEN rejected:=true; END;
    ASSERT rejected,'Rango patológico debe rechazarse, no truncarse';
END;
$$;
RESET ROLE;
ROLLBACK;
