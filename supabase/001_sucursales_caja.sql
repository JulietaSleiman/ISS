-- Ejecutar en SQL Editor con la cuenta propietaria del proyecto.
-- Etapa 1: identidad y cierres. No migra catálogo, ventas ni existencias.
BEGIN;

CREATE TABLE IF NOT EXISTS public.sucursales (
    id uuid PRIMARY KEY,
    nombre text NOT NULL CHECK (length(trim(nombre)) > 0),
    activa boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS public.profiles (
    id uuid PRIMARY KEY REFERENCES auth.users(id),
    username text NOT NULL CHECK (username = lower(username) AND username ~ '^[a-z0-9][a-z0-9_-]{0,49}$'),
    sucursal_id uuid NOT NULL REFERENCES public.sucursales(id),
    nombre text NOT NULL,
    rol text NOT NULL DEFAULT 'cajero' CHECK (rol IN ('cajero', 'admin')),
    activo boolean NOT NULL DEFAULT true,
    UNIQUE (sucursal_id, username),
    UNIQUE (id, sucursal_id)
);

CREATE TABLE IF NOT EXISTS public.cierres_caja (
    id uuid PRIMARY KEY,
    sucursal_id uuid NOT NULL REFERENCES public.sucursales(id),
    responsable_id uuid NOT NULL,
    responsable_nombre text NOT NULL,
    cierre_usuario_id uuid NOT NULL,
    cierre_usuario_nombre text NOT NULL,
    fecha_apertura timestamptz NOT NULL,
    fecha_cierre timestamptz NOT NULL CHECK (fecha_cierre >= fecha_apertura),
    monto_inicial numeric(16,2) NOT NULL CHECK (monto_inicial >= 0 AND monto_inicial <> 'NaN'::numeric),
    monto_esperado numeric(16,2) NOT NULL CHECK (monto_esperado <> 'NaN'::numeric),
    monto_cierre numeric(16,2) NOT NULL CHECK (monto_cierre >= 0 AND monto_cierre <> 'NaN'::numeric),
    diferencia numeric(16,2) NOT NULL,
    resumen jsonb NOT NULL CHECK (jsonb_typeof(resumen) = 'object'),
    recibido_en timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (responsable_id, sucursal_id) REFERENCES public.profiles(id, sucursal_id),
    FOREIGN KEY (cierre_usuario_id, sucursal_id) REFERENCES public.profiles(id, sucursal_id),
    CHECK (diferencia = monto_cierre - monto_esperado)
);
CREATE INDEX IF NOT EXISTS cierres_caja_sucursal_fecha ON public.cierres_caja(sucursal_id, fecha_cierre DESC);

-- Funciones acotadas evitan una política recursiva al consultar profiles.
-- No leen metadata modificable por el usuario ni aceptan roles enviados por la app.
CREATE SCHEMA IF NOT EXISTS iss_private;
REVOKE ALL ON SCHEMA iss_private FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA iss_private TO authenticated;

CREATE OR REPLACE FUNCTION iss_private.is_admin()
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
    SELECT EXISTS (SELECT 1 FROM public.profiles p
                   WHERE p.id = (SELECT auth.uid()) AND p.activo AND p.rol = 'admin');
$$;

CREATE OR REPLACE FUNCTION iss_private.can_read_branch(branch_id uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
    SELECT EXISTS (SELECT 1 FROM public.profiles p
                   WHERE p.id = (SELECT auth.uid()) AND p.activo
                     AND (p.sucursal_id = branch_id OR p.rol = 'admin'));
$$;

CREATE OR REPLACE FUNCTION iss_private.can_insert_close(branch_id uuid, owner_id uuid, actor_id uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
    SELECT actor_id = (SELECT auth.uid()) AND EXISTS (
        SELECT 1 FROM public.profiles p
        JOIN public.sucursales s ON s.id = p.sucursal_id
        WHERE p.id = (SELECT auth.uid()) AND p.activo AND s.activa
          AND p.sucursal_id = branch_id AND (owner_id = p.id OR p.rol = 'admin')
    );
$$;

REVOKE ALL ON FUNCTION iss_private.is_admin() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION iss_private.can_read_branch(uuid) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION iss_private.can_insert_close(uuid, uuid, uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION iss_private.is_admin() TO authenticated;
GRANT EXECUTE ON FUNCTION iss_private.can_read_branch(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION iss_private.can_insert_close(uuid, uuid, uuid) TO authenticated;

ALTER TABLE public.sucursales ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cierres_caja ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.sucursales, public.profiles, public.cierres_caja FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.sucursales, public.profiles, public.cierres_caja TO authenticated;
GRANT INSERT ON public.cierres_caja TO authenticated;

DROP POLICY IF EXISTS sucursales_read ON public.sucursales;
CREATE POLICY sucursales_read ON public.sucursales FOR SELECT TO authenticated
    USING (iss_private.can_read_branch(id));
DROP POLICY IF EXISTS profiles_read ON public.profiles;
CREATE POLICY profiles_read ON public.profiles FOR SELECT TO authenticated
    USING (id = (SELECT auth.uid()) OR iss_private.is_admin());
DROP POLICY IF EXISTS cierres_read ON public.cierres_caja;
CREATE POLICY cierres_read ON public.cierres_caja FOR SELECT TO authenticated
    USING (iss_private.can_read_branch(sucursal_id));
DROP POLICY IF EXISTS cierres_insert ON public.cierres_caja;
CREATE POLICY cierres_insert ON public.cierres_caja FOR INSERT TO authenticated
    WITH CHECK (iss_private.can_insert_close(sucursal_id, responsable_id, cierre_usuario_id));

-- La app no recibe INSERT/UPDATE sobre profiles ni UPDATE/DELETE sobre cierres.
-- Los reintentos usan INSERT ... ON CONFLICT DO NOTHING con el mismo UUID.
INSERT INTO public.sucursales(id, nombre)
VALUES ('f2985c88-2a4e-4e73-92d5-85d905b3db41', 'Estación de Simoca')
ON CONFLICT (id) DO NOTHING;

COMMIT;
