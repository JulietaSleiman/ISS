-- PRUEBA MANUAL: ejecutar únicamente en un proyecto de PRUEBAS con 001 y 004.
-- No ejecutada por Codex: no hay motor PostgreSQL local. Todo termina en ROLLBACK.
-- No crea sesiones Auth ni envía correos. Usa identidades ficticias transaccionales.
BEGIN;
DO $$
DECLARE branch uuid:=gen_random_uuid(); other_branch uuid:=gen_random_uuid();
        cashier uuid:=gen_random_uuid(); admin_id uuid:=gen_random_uuid(); product uuid:=gen_random_uuid();
        data jsonb; envelope jsonb;
BEGIN
    INSERT INTO public.sucursales(id,nombre) VALUES(branch,'Prueba transaccional'),(other_branch,'Otra prueba');
    INSERT INTO auth.users(id,email,aud,role,email_confirmed_at)
        VALUES(cashier,cashier::text||'@usuarios.invalid','authenticated','authenticated',now()),
              (admin_id,admin_id::text||'@usuarios.invalid','authenticated','authenticated',now());
    INSERT INTO public.profiles(id,username,sucursal_id,nombre,rol)
        VALUES(cashier,'prueba',branch,'Operador de prueba','cajero'),
              (admin_id,'adminprueba',branch,'Administrador de prueba','admin');
    data:=jsonb_build_object('id',product,'sucursal_id',branch,'revision',1,'catalog_revision',1,
        'local_id',1,'codigo_barras','PRUEBA','nombre','Producto de prueba','activo',true,
        'costo_lista',5,'flete',0,'costo_final',5,'utilidad_porcentaje',100,
        'precio_contado',10,'precio_tarjeta',12,'stock_actual',20,'stock_minimo',5,
        'stock_maximo',100,'unidades_bulto',1);
    envelope:=jsonb_build_object('id',gen_random_uuid(),'tipo','PRODUCTO','entidad_id',product,
        'revision',1,'usuario_id',cashier,'payload',data);
    PERFORM set_config('iss_test.branch',branch::text,true);
    PERFORM set_config('iss_test.other_branch',other_branch::text,true);
    PERFORM set_config('iss_test.cashier',cashier::text,true);
    PERFORM set_config('iss_test.admin',admin_id::text,true);
    PERFORM set_config('iss_test.product',product::text,true);
    PERFORM set_config('iss_test.envelope',envelope::text,true);
END;
$$;

SET LOCAL ROLE anon;
DO $$
DECLARE rejected boolean:=false;
BEGIN
    BEGIN PERFORM public.sincronizar_entidades('[]'::jsonb);
    EXCEPTION WHEN insufficient_privilege THEN rejected:=true; END;
    ASSERT rejected,'anon no debe poder ejecutar sincronización';
END;
$$;
RESET ROLE;
SELECT set_config('request.jwt.claim.sub',current_setting('iss_test.cashier'),true);
SET LOCAL ROLE authenticated;
DO $$
DECLARE event jsonb:=current_setting('iss_test.envelope')::jsonb; newer jsonb; stale jsonb;
        result jsonb; rejected boolean; total_stock numeric; current_rev bigint;
BEGIN
    result:=public.sincronizar_entidades(jsonb_build_array(event),0);
    ASSERT jsonb_array_length(result->'acknowledged')=1,'Falta ACK';
    PERFORM public.sincronizar_entidades(jsonb_build_array(event),0); -- ACK perdido: mismo UUID.
    newer:=jsonb_set(event,'{id}',to_jsonb(gen_random_uuid()));
    newer:=jsonb_set(newer,'{revision}','3'::jsonb);
    newer:=jsonb_set(newer,'{payload,revision}','3'::jsonb);
    newer:=jsonb_set(newer,'{payload,stock_actual}','15'::jsonb);
    PERFORM public.sincronizar_entidades(jsonb_build_array(newer),0);
    stale:=jsonb_set(event,'{id}',to_jsonb(gen_random_uuid()));
    stale:=jsonb_set(stale,'{revision}','2'::jsonb);
    stale:=jsonb_set(stale,'{payload,revision}','2'::jsonb);
    stale:=jsonb_set(stale,'{payload,stock_actual}','18'::jsonb);
    PERFORM public.sincronizar_entidades(jsonb_build_array(stale),0);
    SELECT stock_actual,revision INTO total_stock,current_rev FROM public.productos_sucursal
        WHERE sucursal_id=current_setting('iss_test.branch')::uuid AND id=current_setting('iss_test.product')::uuid;
    ASSERT total_stock=15 AND current_rev=3,'Una revisión antigua no debe restaurar stock ni descontarlo otra vez';
    rejected:=false;
    BEGIN PERFORM public.sincronizar_entidades(jsonb_build_array(jsonb_set(event,'{payload,stock_actual}','99'::jsonb)),0);
    EXCEPTION WHEN others THEN rejected:=true; END;
    ASSERT rejected,'Un UUID reutilizado con datos diferentes debe rechazarse';
    rejected:=false;
    BEGIN PERFORM public.sincronizar_entidades(jsonb_build_array(jsonb_set(event,'{payload,sucursal_id}',to_jsonb(current_setting('iss_test.other_branch')))),0);
    EXCEPTION WHEN insufficient_privilege THEN rejected:=true; END;
    ASSERT rejected,'No debe escribir otra sucursal';
    rejected:=false;
    BEGIN PERFORM public.resumen_central();
    EXCEPTION WHEN insufficient_privilege THEN rejected:=true; END;
    ASSERT rejected,'Cajero no debe consultar administración central';
    rejected:=false;
    BEGIN INSERT INTO public.productos_sucursal(sucursal_id,id) VALUES(current_setting('iss_test.branch')::uuid,gen_random_uuid());
    EXCEPTION WHEN insufficient_privilege THEN rejected:=true; END;
    ASSERT rejected,'No debe haber escritura directa al catálogo remoto';
END;
$$;
RESET ROLE;
SELECT set_config('request.jwt.claim.sub',current_setting('iss_test.admin'),true);
SET LOCAL ROLE authenticated;
DO $$
DECLARE command jsonb; dashboard jsonb;
BEGIN
    dashboard:=public.resumen_central(current_setting('iss_test.branch')::uuid);
    ASSERT (dashboard->'totals'->>'productos_count')::integer=1,'Resumen debe calcular en servidor';
    command:=public.solicitar_cambio_precios(current_setting('iss_test.branch')::uuid,
        current_setting('iss_test.product')::uuid,1,15,18);
    ASSERT command->>'estado'='PENDIENTE','Una solicitud no equivale a un precio ya aplicado';
    PERFORM set_config('iss_test.command',command::text,true);
END;
$$;
RESET ROLE;
SELECT set_config('request.jwt.claim.sub',current_setting('iss_test.cashier'),true);
SET LOCAL ROLE authenticated;
DO $$
DECLARE command jsonb:=current_setting('iss_test.command')::jsonb; receipt jsonb; result jsonb;
BEGIN
    receipt:=jsonb_build_object('command_id',command->>'id','status','CONFLICTO','detail','Prueba de conflicto');
    result:=public.confirmar_comandos_precios(jsonb_build_array(receipt));
    ASSERT jsonb_array_length(result->'acknowledged')=1,'Falta ACK de comando';
    PERFORM public.confirmar_comandos_precios(jsonb_build_array(receipt)); -- Confirmación repetida.
END;
$$;
RESET ROLE;
ROLLBACK;
