-- PRUEBA MANUAL solo en proyecto de PRUEBAS, como propietario, tras 001/004/007.
-- No ejecutada por Codex: no hay motor PostgreSQL local.
-- Aplicar 007 dos veces antes y comprobar que conserva códigos ya asignados.
-- Este smoke valida restricciones y acceso efectivo; todos sus datos se revierten.
BEGIN;
DO $$
DECLARE branch uuid := gen_random_uuid(); other_branch uuid := gen_random_uuid();
        cashier uuid := gen_random_uuid(); code text; invalid text; rejected boolean;
BEGIN
    code := 'prueba-' || replace(branch::text, '-', '');
    INSERT INTO public.sucursales(id,nombre,codigo)
        VALUES (branch,'Código de prueba',code),(other_branch,'Legacy sin código',NULL);
    -- NULL no identifica una sucursal: varias instalaciones antiguas pueden conservarlo.
    INSERT INTO public.sucursales(id,nombre,codigo) VALUES(gen_random_uuid(),'Otra legacy',NULL);
    INSERT INTO public.sucursales(id,nombre,codigo)
        VALUES(gen_random_uuid(),'Límite mínimo','0'),
              (gen_random_uuid(),'Límite máximo',repeat('z',48))
        ON CONFLICT DO NOTHING;
    rejected := false;
    BEGIN
        INSERT INTO public.sucursales(id,nombre,codigo) VALUES(gen_random_uuid(),'Duplicada',code);
    EXCEPTION WHEN unique_violation THEN rejected := true;
    END;
    ASSERT rejected, 'Debe rechazar dos sucursales con el mismo código';

    FOREACH invalid IN ARRAY ARRAY['', 'MAYUSCULA', 'con espacio', 'simóca',
        '-inicio', 'final-', 'doble--guion', 'punto.codigo', repeat('a',49), 'linea'||chr(10)] LOOP
        rejected := false;
        BEGIN
            INSERT INTO public.sucursales(id,nombre,codigo)
                VALUES(gen_random_uuid(),'Formato inválido',invalid);
        EXCEPTION WHEN check_violation THEN rejected := true;
        END;
        ASSERT rejected, 'Debe rechazar formato: ' || quote_literal(invalid);
    END LOOP;

    -- Cambiar el nombre visible mantiene el identificador público estable.
    UPDATE public.sucursales SET nombre='Nuevo nombre visible' WHERE id=branch;
    ASSERT (SELECT codigo=code FROM public.sucursales WHERE id=branch), 'Renombrar no cambia código';

    INSERT INTO auth.users(id,email,aud,role,email_confirmed_at)
        VALUES(cashier,'caja1.'||code||'@usuarios.invalid','authenticated','authenticated',now());
    INSERT INTO public.profiles(id,username,sucursal_id,nombre,rol)
        VALUES(cashier,'caja1',branch,'Operador de prueba','cajero');
    PERFORM set_config('iss_test.branch',branch::text,true);
    PERFORM set_config('iss_test.other_branch',other_branch::text,true);
    PERFORM set_config('iss_test.cashier',cashier::text,true);
    PERFORM set_config('iss_test.code',code,true);
END;
$$;

SET LOCAL ROLE anon;
DO $$
DECLARE rejected boolean := false;
BEGIN
    BEGIN PERFORM codigo FROM public.sucursales;
    EXCEPTION WHEN insufficient_privilege THEN rejected := true;
    END;
    ASSERT rejected, 'anon no puede consultar códigos';
END;
$$;
RESET ROLE;

SELECT set_config('request.jwt.claim.sub',current_setting('iss_test.cashier'),true);
SET LOCAL ROLE authenticated;
DO $$
BEGIN
    ASSERT (SELECT codigo=current_setting('iss_test.code') FROM public.sucursales
        WHERE id=current_setting('iss_test.branch')::uuid), 'JWT propio debe poder leer código';
    ASSERT NOT EXISTS (SELECT 1 FROM public.sucursales
        WHERE id=current_setting('iss_test.other_branch')::uuid), 'Cajero no debe leer otra sucursal';
END;
$$;
RESET ROLE;
ROLLBACK;
