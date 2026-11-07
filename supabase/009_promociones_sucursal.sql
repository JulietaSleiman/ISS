BEGIN;

CREATE TABLE IF NOT EXISTS public.promociones_sucursal (
    sucursal_id uuid NOT NULL REFERENCES public.sucursales(id),
    id uuid NOT NULL,
    revision bigint NOT NULL CHECK (revision > 0),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    PRIMARY KEY (sucursal_id, id)
);

ALTER TABLE public.promociones_sucursal ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.promociones_sucursal FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.promociones_sucursal TO authenticated;
DROP POLICY IF EXISTS promociones_sucursal_read ON public.promociones_sucursal;
CREATE POLICY promociones_sucursal_read ON public.promociones_sucursal FOR SELECT TO authenticated
    USING (iss_private.can_read_branch(sucursal_id));

CREATE OR REPLACE FUNCTION public.guardar_promocion_sucursal(
    p_sucursal uuid, p_id uuid, p_revision bigint, p_payload jsonb
) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.profiles p JOIN public.sucursales s ON s.id = p.sucursal_id
        WHERE p.id = (SELECT auth.uid()) AND p.activo AND s.activa
          AND p.sucursal_id = p_sucursal AND p.rol IN ('cajero', 'admin')
    ) THEN
        RAISE EXCEPTION 'Usuario sin acceso de escritura a la sucursal';
    END IF;
    IF nullif(btrim(p_payload->>'nombre'), '') IS NULL
        OR jsonb_typeof(p_payload->'precio_fijo') IS DISTINCT FROM 'number'
        OR (p_payload->>'precio_fijo')::numeric < 0
        OR jsonb_typeof(p_payload->'activa') IS DISTINCT FROM 'boolean'
        OR jsonb_typeof(p_payload->'detalles') IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'Promoción inválida';
    END IF;
    IF EXISTS (
        SELECT 1 FROM jsonb_array_elements(p_payload->'detalles') AS items(detalle)
        WHERE jsonb_typeof(detalle->'cantidad_requerida') IS DISTINCT FROM 'number'
           OR (detalle->>'cantidad_requerida')::numeric <= 0
           OR NOT EXISTS (
               SELECT 1 FROM public.productos_sucursal p
               WHERE p.sucursal_id = p_sucursal AND p.id = (detalle->>'producto')::uuid
           )
    ) THEN
        RAISE EXCEPTION 'La promoción contiene productos sin sincronizar o cantidades inválidas';
    END IF;
    INSERT INTO public.promociones_sucursal AS current_promo(sucursal_id, id, revision, payload)
    VALUES (p_sucursal, p_id, p_revision, p_payload)
    ON CONFLICT (sucursal_id, id) DO UPDATE
        SET revision = excluded.revision, payload = excluded.payload
        WHERE current_promo.revision < excluded.revision
           OR (current_promo.revision = excluded.revision AND current_promo.payload = excluded.payload);
    RETURN FOUND;
END;
$$;

REVOKE ALL ON FUNCTION public.guardar_promocion_sucursal(uuid, uuid, bigint, jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.guardar_promocion_sucursal(uuid, uuid, bigint, jsonb) TO authenticated;
COMMIT;
