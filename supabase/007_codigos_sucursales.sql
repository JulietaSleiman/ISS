-- Ejecutar con la cuenta propietaria DESPUÉS de 001 y 004. Se puede repetir.
-- El código es un identificador PÚBLICO, no una contraseña ni una autorización.
-- Es estable: cambiar nombre es seguro; cambiar código requiere migrar cuentas Auth
-- y configuraciones de las instalaciones existentes de manera coordinada.
BEGIN;

ALTER TABLE public.sucursales ADD COLUMN IF NOT EXISTS codigo text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.sucursales'::regclass
          AND conname = 'sucursales_codigo_formato'
    ) THEN
        ALTER TABLE public.sucursales ADD CONSTRAINT sucursales_codigo_formato
            CHECK (codigo IS NULL OR (
                char_length(codigo) BETWEEN 1 AND 48
                AND codigo COLLATE "C" ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
            ));
    END IF;
END;
$$;

-- Otras sucursales históricas siguen sin código hasta su asignación explícita.
CREATE UNIQUE INDEX IF NOT EXISTS sucursales_codigo_unico
    ON public.sucursales(codigo) WHERE codigo IS NOT NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.sucursales
        WHERE id = 'f2985c88-2a4e-4e73-92d5-85d905b3db41'::uuid AND codigo IS NULL
    ) THEN
        IF EXISTS (
            SELECT 1 FROM public.sucursales
            WHERE codigo = 'estacion-de-simoca'
              AND id <> 'f2985c88-2a4e-4e73-92d5-85d905b3db41'::uuid
        ) THEN
            RAISE EXCEPTION 'El código estacion-de-simoca ya pertenece a otra sucursal; revise la asignación antes de repetir 007'
                USING ERRCODE = '23505';
        END IF;
        UPDATE public.sucursales SET codigo = 'estacion-de-simoca'
            WHERE id = 'f2985c88-2a4e-4e73-92d5-85d905b3db41'::uuid AND codigo IS NULL;
    END IF;
END;
$$;

-- No se cambian RLS, políticas ni privilegios. El JWT y el perfil autorizado
-- permiten consultar la sucursal correspondiente; anon no puede descubrir códigos.
NOTIFY pgrst, 'reload schema';
COMMIT;

-- ALTA MANUAL DE OTRA SUCURSAL (ejemplo, NO ejecutar sin adaptar):
-- INSERT INTO public.sucursales(id, nombre, codigo)
-- VALUES (gen_random_uuid(), 'Sucursal ejemplo', 'sucursal-ejemplo')
-- RETURNING id, nombre, codigo;
-- Crear el usuario desde Authentication > Users del Dashboard de Supabase:
-- correo caja1.sucursal-ejemplo@usuarios.invalid y contraseña privada elegida allí.
-- Asignar manualmente su public.profiles.sucursal_id al UUID retornado, username
-- 'caja1' y rol 'cajero' (ver 002). Administradores también se crean manualmente
-- en Dashboard y reciben perfil explícito (ver 005); no compilar claves administrativas.
-- El código introducido en una PC nueva solo sirve para formar el correo de acceso.
-- Después de autenticar, la app obtiene el código del servidor con JWT y comprueba
-- que sucursal, código y perfil coincidan antes de vincular la instalación.
