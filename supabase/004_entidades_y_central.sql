-- Etapa 2. Ejecutar DESPUÉS de 001 con la cuenta propietaria, en SQL Editor.
-- Instantáneas por sucursal: un reintento nunca vuelve a descontar existencias.
BEGIN;

CREATE TABLE IF NOT EXISTS public.productos_sucursal (
    sucursal_id uuid NOT NULL REFERENCES public.sucursales(id),
    id uuid NOT NULL,
    revision bigint NOT NULL CHECK (revision > 0),
    catalog_revision bigint NOT NULL CHECK (catalog_revision > 0),
    local_id bigint NOT NULL CHECK (local_id > 0),
    codigo_barras text,
    nombre text NOT NULL CHECK (length(trim(nombre)) > 0),
    precio_contado numeric(16,2) NOT NULL CHECK (precio_contado >= 0 AND precio_contado <> 'NaN'::numeric),
    precio_tarjeta numeric(16,2) NOT NULL CHECK (precio_tarjeta >= 0 AND precio_tarjeta <> 'NaN'::numeric),
    stock_actual numeric(20,4) NOT NULL CHECK (stock_actual <> 'NaN'::numeric),
    stock_minimo numeric(20,4) NOT NULL CHECK (stock_minimo <> 'NaN'::numeric),
    activo boolean NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    synced_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (sucursal_id, id)
);
CREATE TABLE IF NOT EXISTS public.ventas_sucursal (
    sucursal_id uuid NOT NULL REFERENCES public.sucursales(id),
    id uuid NOT NULL,
    revision bigint NOT NULL CHECK (revision > 0),
    local_id bigint NOT NULL CHECK (local_id > 0),
    fecha timestamptz NOT NULL,
    subtotal numeric(16,2) NOT NULL CHECK (subtotal >= 0 AND subtotal <> 'NaN'::numeric),
    descuento_total numeric(16,2) NOT NULL CHECK (descuento_total >= 0 AND descuento_total <> 'NaN'::numeric),
    total numeric(16,2) NOT NULL CHECK (total >= 0 AND total <> 'NaN'::numeric),
    metodo_pago text NOT NULL,
    estado text NOT NULL,
    cliente_nombre text,
    vendedor_id uuid,
    historica boolean NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload->'detalles') = 'array'),
    synced_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (sucursal_id, id),
    FOREIGN KEY (vendedor_id, sucursal_id) REFERENCES public.profiles(id, sucursal_id),
    CHECK ((historica AND vendedor_id IS NULL) OR (NOT historica AND vendedor_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ventas_sucursal_fecha ON public.ventas_sucursal(sucursal_id, fecha DESC, id);
CREATE TABLE IF NOT EXISTS public.sucursales_estado (
    sucursal_id uuid PRIMARY KEY REFERENCES public.sucursales(id),
    last_sync_at timestamptz NOT NULL,
    pendientes bigint NOT NULL DEFAULT 0 CHECK (pendientes >= 0)
);
CREATE TABLE IF NOT EXISTS public.sync_eventos_recibidos (
    id uuid PRIMARY KEY,
    sucursal_id uuid NOT NULL REFERENCES public.sucursales(id),
    entidad_id uuid NOT NULL,
    tipo text NOT NULL CHECK (tipo IN ('PRODUCTO','VENTA')),
    revision bigint NOT NULL CHECK (revision > 0),
    usuario_id uuid NOT NULL,
    envelope jsonb NOT NULL,
    recibido_en timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (usuario_id, sucursal_id) REFERENCES public.profiles(id, sucursal_id)
);
-- Se conservan eventos/UUID para deduplicar y auditar. No hay borrado desde la app.
CREATE INDEX IF NOT EXISTS sync_eventos_recibidos_fecha ON public.sync_eventos_recibidos(recibido_en);
CREATE TABLE IF NOT EXISTS public.comandos_precios (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sucursal_id uuid NOT NULL,
    producto_id uuid NOT NULL,
    expected_catalog_revision bigint NOT NULL CHECK (expected_catalog_revision > 0),
    precio_contado numeric(16,2) NOT NULL CHECK (precio_contado >= 0 AND precio_contado <> 'NaN'::numeric),
    precio_tarjeta numeric(16,2) NOT NULL CHECK (precio_tarjeta >= 0 AND precio_tarjeta <> 'NaN'::numeric),
    estado text NOT NULL DEFAULT 'PENDIENTE' CHECK (estado IN ('PENDIENTE','APLICADO','CONFLICTO','NO_ENCONTRADO')),
    requested_by uuid NOT NULL REFERENCES auth.users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    acked_at timestamptz,
    detail text,
    FOREIGN KEY (sucursal_id, producto_id) REFERENCES public.productos_sucursal(sucursal_id, id)
);
CREATE UNIQUE INDEX IF NOT EXISTS comando_precio_pendiente
    ON public.comandos_precios(sucursal_id, producto_id) WHERE estado = 'PENDIENTE';
CREATE INDEX IF NOT EXISTS comandos_precios_pendientes ON public.comandos_precios(sucursal_id, estado, created_at, id);

ALTER TABLE public.productos_sucursal ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ventas_sucursal ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sucursales_estado ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sync_eventos_recibidos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.comandos_precios ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.productos_sucursal, public.ventas_sucursal, public.sucursales_estado,
    public.sync_eventos_recibidos, public.comandos_precios FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.productos_sucursal, public.ventas_sucursal,
    public.sucursales_estado, public.comandos_precios TO authenticated;
DROP POLICY IF EXISTS productos_sucursal_read ON public.productos_sucursal;
CREATE POLICY productos_sucursal_read ON public.productos_sucursal FOR SELECT TO authenticated
    USING (iss_private.can_read_branch(sucursal_id));
DROP POLICY IF EXISTS ventas_sucursal_read ON public.ventas_sucursal;
CREATE POLICY ventas_sucursal_read ON public.ventas_sucursal FOR SELECT TO authenticated
    USING (iss_private.can_read_branch(sucursal_id));
DROP POLICY IF EXISTS sucursales_estado_read ON public.sucursales_estado;
CREATE POLICY sucursales_estado_read ON public.sucursales_estado FOR SELECT TO authenticated
    USING (iss_private.can_read_branch(sucursal_id));
DROP POLICY IF EXISTS comandos_precios_read ON public.comandos_precios;
CREATE POLICY comandos_precios_read ON public.comandos_precios FOR SELECT TO authenticated
    USING (iss_private.can_read_branch(sucursal_id));

CREATE OR REPLACE FUNCTION public.sincronizar_entidades(p_eventos jsonb,p_pendientes bigint DEFAULT 0)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE
    actor public.profiles%ROWTYPE;
    evento jsonb; datos jsonb; original jsonb;
    event_id uuid; entity_id uuid; owner_id uuid; event_type text; rev bigint;
    inserted_id uuid; existing_rev bigint; existing_payload jsonb;
    acknowledged jsonb := '[]'::jsonb;
    key_name text; amount numeric;
BEGIN
    SELECT p.* INTO actor FROM public.profiles p JOIN public.sucursales s ON s.id = p.sucursal_id
        WHERE p.id = (SELECT auth.uid()) AND p.activo AND s.activa;
    IF NOT FOUND THEN RAISE EXCEPTION 'Usuario o sucursal no habilitados' USING ERRCODE = '42501'; END IF;
    IF p_eventos IS NULL OR jsonb_typeof(p_eventos) <> 'array' OR jsonb_array_length(p_eventos) > 50
        OR p_pendientes IS NULL OR p_pendientes < 0 THEN
        RAISE EXCEPTION 'Se requiere una lista de hasta 50 eventos';
    END IF;
    FOR evento IN SELECT value FROM jsonb_array_elements(p_eventos) LOOP
        datos := evento->'payload';
        event_id := (evento->>'id')::uuid;
        entity_id := (evento->>'entidad_id')::uuid;
        owner_id := (evento->>'usuario_id')::uuid;
        event_type := evento->>'tipo';
        rev := (evento->>'revision')::bigint;
        IF event_id IS NULL OR entity_id IS NULL OR rev IS NULL OR rev <= 0 OR
           event_type IS NULL OR event_type NOT IN ('PRODUCTO','VENTA') OR
           datos IS NULL OR jsonb_typeof(datos) <> 'object' OR
           (datos->>'sucursal_id')::uuid IS DISTINCT FROM actor.sucursal_id OR
           (datos->>'id')::uuid IS DISTINCT FROM entity_id OR
           (datos->>'revision')::bigint IS DISTINCT FROM rev THEN
            RAISE EXCEPTION 'Evento o sucursal inválidos' USING ERRCODE = '42501';
        END IF;
        IF owner_id IS NULL OR (owner_id <> actor.id AND actor.rol <> 'admin') OR NOT EXISTS (
            SELECT 1 FROM public.profiles p WHERE p.id = owner_id AND p.sucursal_id = actor.sucursal_id
        ) THEN RAISE EXCEPTION 'Autor del evento no autorizado' USING ERRCODE = '42501'; END IF;
        IF (datos->>'local_id')::bigint IS NULL OR (datos->>'local_id')::bigint <= 0 THEN
            RAISE EXCEPTION 'Identificador local inválido';
        END IF;
        -- El UUID global y el envelope íntegro hacen verificables los reintentos.
        inserted_id := NULL;
        INSERT INTO public.sync_eventos_recibidos(id, sucursal_id, entidad_id, tipo, revision, usuario_id, envelope)
            VALUES (event_id, actor.sucursal_id, entity_id, event_type, rev, owner_id, evento)
            ON CONFLICT (id) DO NOTHING RETURNING id INTO inserted_id;
        IF inserted_id IS NULL THEN
            SELECT envelope INTO original FROM public.sync_eventos_recibidos WHERE id = event_id;
            IF original IS DISTINCT FROM evento THEN RAISE EXCEPTION 'UUID de evento reutilizado con datos diferentes'; END IF;
            acknowledged := acknowledged || jsonb_build_array(event_id);
            CONTINUE;
        END IF;
        -- Serializa las revisiones aun cuando todavía no existe una fila del producto.
        PERFORM pg_advisory_xact_lock(hashtextextended(actor.sucursal_id::text || event_type || entity_id::text, 0));
        IF event_type = 'PRODUCTO' THEN
            FOREACH key_name IN ARRAY ARRAY['costo_lista','flete','costo_final','utilidad_porcentaje',
                    'precio_contado','precio_tarjeta','stock_actual','stock_minimo','stock_maximo','unidades_bulto'] LOOP
                IF jsonb_typeof(datos->key_name) IS DISTINCT FROM 'number' THEN RAISE EXCEPTION 'Importe de producto inválido'; END IF;
                amount := (datos->>key_name)::numeric;
                IF amount IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric) OR abs(amount) >= 100000000000000 THEN
                    RAISE EXCEPTION 'Importe de producto fuera de rango';
                END IF;
            END LOOP;
            IF (datos->>'precio_contado')::numeric < 0 OR (datos->>'precio_tarjeta')::numeric < 0 OR
                jsonb_typeof(datos->'activo') IS DISTINCT FROM 'boolean' OR
                NULLIF(trim(datos->>'nombre'),'') IS NULL OR
                (datos->>'catalog_revision')::bigint IS NULL OR (datos->>'catalog_revision')::bigint <= 0 THEN
                RAISE EXCEPTION 'Catálogo inválido';
            END IF;
            SELECT revision, payload INTO existing_rev, existing_payload FROM public.productos_sucursal
                WHERE sucursal_id = actor.sucursal_id AND id = entity_id FOR UPDATE;
            IF existing_rev = rev AND existing_payload IS DISTINCT FROM datos THEN
                RAISE EXCEPTION 'Revisión de producto reutilizada con datos diferentes';
            END IF;
            IF existing_rev IS NULL OR rev > existing_rev THEN
                IF existing_rev IS NOT NULL AND (datos->>'catalog_revision')::bigint < (existing_payload->>'catalog_revision')::bigint THEN
                    RAISE EXCEPTION 'La revisión de catálogo no puede retroceder';
                END IF;
                IF existing_rev IS NOT NULL AND (datos->>'catalog_revision')::bigint = (existing_payload->>'catalog_revision')::bigint
                    AND ((datos->>'precio_contado')::numeric IS DISTINCT FROM (existing_payload->>'precio_contado')::numeric
                      OR (datos->>'precio_tarjeta')::numeric IS DISTINCT FROM (existing_payload->>'precio_tarjeta')::numeric) THEN
                    RAISE EXCEPTION 'El cambio de precios requiere una nueva revisión de catálogo';
                END IF;
                INSERT INTO public.productos_sucursal
                    (sucursal_id,id,revision,catalog_revision,local_id,codigo_barras,nombre,
                     precio_contado,precio_tarjeta,stock_actual,stock_minimo,activo,payload)
                VALUES (actor.sucursal_id,entity_id,rev,(datos->>'catalog_revision')::bigint,
                    (datos->>'local_id')::bigint,datos->>'codigo_barras',datos->>'nombre',
                    (datos->>'precio_contado')::numeric,(datos->>'precio_tarjeta')::numeric,
                    (datos->>'stock_actual')::numeric,(datos->>'stock_minimo')::numeric,
                    (datos->>'activo')::boolean,datos)
                ON CONFLICT (sucursal_id,id) DO UPDATE SET
                    revision=EXCLUDED.revision,catalog_revision=EXCLUDED.catalog_revision,
                    local_id=EXCLUDED.local_id,codigo_barras=EXCLUDED.codigo_barras,nombre=EXCLUDED.nombre,
                    precio_contado=EXCLUDED.precio_contado,precio_tarjeta=EXCLUDED.precio_tarjeta,
                    stock_actual=EXCLUDED.stock_actual,stock_minimo=EXCLUDED.stock_minimo,
                    activo=EXCLUDED.activo,payload=EXCLUDED.payload,synced_at=now();
            END IF;
        ELSE
            FOREACH key_name IN ARRAY ARRAY['subtotal','descuento_total','total'] LOOP
                IF jsonb_typeof(datos->key_name) IS DISTINCT FROM 'number' THEN RAISE EXCEPTION 'Importe de venta inválido'; END IF;
                amount := (datos->>key_name)::numeric;
                IF amount < 0 OR amount IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)
                    OR amount >= 100000000000000 THEN RAISE EXCEPTION 'Importe de venta fuera de rango'; END IF;
            END LOOP;
            IF jsonb_typeof(datos->'detalles') IS DISTINCT FROM 'array' OR
               jsonb_typeof(datos->'historica') IS DISTINCT FROM 'boolean' OR
               NULLIF(datos->>'fecha','') IS NULL OR NULLIF(datos->>'estado','') IS NULL OR
               NULLIF(datos->>'metodo_pago','') IS NULL OR NOT isfinite((datos->>'fecha')::timestamptz) THEN
                RAISE EXCEPTION 'Venta inválida';
            END IF;
            IF (datos->>'historica')::boolean IS DISTINCT FROM ((datos->>'vendedor_id') IS NULL) THEN
                RAISE EXCEPTION 'Una venta histórica no puede atribuirse a un vendedor inventado';
            END IF;
            SELECT revision, payload INTO existing_rev, existing_payload FROM public.ventas_sucursal
                WHERE sucursal_id = actor.sucursal_id AND id = entity_id FOR UPDATE;
            IF existing_rev IS NULL AND NOT (datos->>'historica')::boolean
                AND (datos->>'vendedor_id')::uuid IS DISTINCT FROM owner_id THEN
                RAISE EXCEPTION 'El vendedor debe coincidir con el autor original del evento' USING ERRCODE='42501';
            END IF;
            IF existing_rev = rev AND existing_payload IS DISTINCT FROM datos THEN
                RAISE EXCEPTION 'Revisión de venta reutilizada con datos diferentes';
            END IF;
            IF existing_rev IS NULL OR rev > existing_rev THEN
                IF existing_rev IS NOT NULL AND
                    (datos-ARRAY['revision','estado']) IS DISTINCT FROM (existing_payload-ARRAY['revision','estado']) THEN
                    RAISE EXCEPTION 'Una venta registrada conserva su fecha, vendedor, importes y detalle originales';
                END IF;
                INSERT INTO public.ventas_sucursal(sucursal_id,id,revision,local_id,fecha,subtotal,
                    descuento_total,total,metodo_pago,estado,cliente_nombre,vendedor_id,historica,payload)
                VALUES (actor.sucursal_id,entity_id,rev,(datos->>'local_id')::bigint,(datos->>'fecha')::timestamptz,
                    (datos->>'subtotal')::numeric,(datos->>'descuento_total')::numeric,(datos->>'total')::numeric,
                    datos->>'metodo_pago',datos->>'estado',datos->>'cliente_nombre',(datos->>'vendedor_id')::uuid,
                    (datos->>'historica')::boolean,datos)
                ON CONFLICT (sucursal_id,id) DO UPDATE SET revision=EXCLUDED.revision,local_id=EXCLUDED.local_id,
                    fecha=EXCLUDED.fecha,subtotal=EXCLUDED.subtotal,descuento_total=EXCLUDED.descuento_total,
                    total=EXCLUDED.total,metodo_pago=EXCLUDED.metodo_pago,estado=EXCLUDED.estado,
                    cliente_nombre=EXCLUDED.cliente_nombre,vendedor_id=EXCLUDED.vendedor_id,
                    historica=EXCLUDED.historica,payload=EXCLUDED.payload,synced_at=now();
            END IF;
        END IF;
        acknowledged := acknowledged || jsonb_build_array(event_id);
    END LOOP;
    INSERT INTO public.sucursales_estado(sucursal_id,last_sync_at,pendientes)
        VALUES (actor.sucursal_id,now(),p_pendientes)
        ON CONFLICT (sucursal_id) DO UPDATE SET last_sync_at=EXCLUDED.last_sync_at,pendientes=EXCLUDED.pendientes;
    RETURN jsonb_build_object('acknowledged',acknowledged,'server_time',now());
END;
$$;

CREATE OR REPLACE FUNCTION public.solicitar_cambio_precios(p_sucursal_id uuid,p_producto_id uuid,
    p_expected_catalog_revision bigint,p_precio_contado numeric,p_precio_tarjeta numeric)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE product public.productos_sucursal%ROWTYPE; command public.comandos_precios%ROWTYPE;
BEGIN
    IF NOT iss_private.is_admin() THEN RAISE EXCEPTION 'Se requiere administrador' USING ERRCODE='42501'; END IF;
    IF p_precio_contado IS NULL OR p_precio_tarjeta IS NULL OR p_precio_contado < 0 OR p_precio_tarjeta < 0 OR
       p_precio_contado IN ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric) OR
       p_precio_tarjeta IN ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric) OR
       p_precio_contado >= 100000000000000 OR p_precio_tarjeta >= 100000000000000 THEN
        RAISE EXCEPTION 'Precios inválidos'; END IF;
    IF NOT EXISTS (SELECT 1 FROM public.sucursales WHERE id=p_sucursal_id AND activa) THEN
        RAISE EXCEPTION 'Sucursal no habilitada'; END IF;
    SELECT * INTO product FROM public.productos_sucursal WHERE sucursal_id=p_sucursal_id AND id=p_producto_id FOR UPDATE;
    IF NOT FOUND OR NOT product.activo THEN RAISE EXCEPTION 'Producto no disponible'; END IF;
    IF product.catalog_revision IS DISTINCT FROM p_expected_catalog_revision THEN
        RAISE EXCEPTION 'El catálogo cambió. Actualice antes de solicitar precios'; END IF;
    INSERT INTO public.comandos_precios(sucursal_id,producto_id,expected_catalog_revision,precio_contado,precio_tarjeta,requested_by)
        VALUES(p_sucursal_id,p_producto_id,p_expected_catalog_revision,p_precio_contado,p_precio_tarjeta,(SELECT auth.uid()))
        RETURNING * INTO command;
    RETURN to_jsonb(command);
END;
$$;

CREATE OR REPLACE FUNCTION public.confirmar_comandos_precios(p_resultados jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE actor public.profiles%ROWTYPE; result jsonb; command public.comandos_precios%ROWTYPE;
        acknowledged jsonb := '[]'::jsonb;
BEGIN
    SELECT p.* INTO actor FROM public.profiles p JOIN public.sucursales s ON s.id=p.sucursal_id
        WHERE p.id=(SELECT auth.uid()) AND p.activo AND s.activa;
    IF NOT FOUND THEN RAISE EXCEPTION 'Usuario no habilitado' USING ERRCODE='42501'; END IF;
    IF p_resultados IS NULL OR jsonb_typeof(p_resultados)<>'array' OR jsonb_array_length(p_resultados)>50 THEN
        RAISE EXCEPTION 'Se requiere lista de hasta 50 confirmaciones'; END IF;
    FOR result IN SELECT value FROM jsonb_array_elements(p_resultados) LOOP
        IF result->>'status' IS NULL OR result->>'status' NOT IN ('APLICADO','CONFLICTO','NO_ENCONTRADO') THEN
            RAISE EXCEPTION 'Estado de confirmación inválido'; END IF;
        SELECT * INTO command FROM public.comandos_precios WHERE id=(result->>'command_id')::uuid FOR UPDATE;
        IF NOT FOUND OR command.sucursal_id <> actor.sucursal_id THEN
            RAISE EXCEPTION 'Comando ajeno a la sucursal' USING ERRCODE='42501'; END IF;
        IF command.estado <> 'PENDIENTE' THEN
            IF command.estado IS DISTINCT FROM result->>'status' OR command.detail IS DISTINCT FROM left(result->>'detail',2000) THEN
                RAISE EXCEPTION 'Confirmación distinta de la registrada'; END IF;
        ELSE
            UPDATE public.comandos_precios SET estado=result->>'status', detail=left(result->>'detail',2000),acked_at=now()
                WHERE id=command.id;
        END IF;
        acknowledged := acknowledged || jsonb_build_array(command.id);
    END LOOP;
    RETURN jsonb_build_object('acknowledged',acknowledged,'server_time',now());
END;
$$;

CREATE OR REPLACE FUNCTION public.resumen_central(p_sucursal_id uuid DEFAULT NULL,
    p_fecha_desde date DEFAULT NULL,p_fecha_hasta date DEFAULT NULL)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
DECLARE result jsonb; from_time timestamptz; until_time timestamptz;
BEGIN
    IF NOT iss_private.is_admin() THEN RAISE EXCEPTION 'Se requiere administrador' USING ERRCODE='42501'; END IF;
    IF p_fecha_desde > p_fecha_hasta THEN RAISE EXCEPTION 'Rango de fechas inválido'; END IF;
    from_time := p_fecha_desde::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires';
    until_time := (p_fecha_hasta+1)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires';
    WITH sales AS (
        SELECT sucursal_id,count(*) AS ventas_count,coalesce(sum(total),0) AS total_vendido
        FROM public.ventas_sucursal WHERE estado<>'CANCELADA'
          AND (from_time IS NULL OR fecha>=from_time) AND (until_time IS NULL OR fecha<until_time)
        GROUP BY sucursal_id
    ), products AS (
        SELECT sucursal_id,count(*) AS productos_count,count(*) FILTER(WHERE stock_actual<=stock_minimo) AS alertas_stock
        FROM public.productos_sucursal WHERE activo GROUP BY sucursal_id
    ), cash AS (
        SELECT sucursal_id,count(*) AS cierres_count,coalesce(sum(diferencia),0) AS diferencias
        FROM public.cierres_caja WHERE (from_time IS NULL OR fecha_cierre>=from_time)
          AND (until_time IS NULL OR fecha_cierre<until_time) GROUP BY sucursal_id
    ), branches AS (
        SELECT s.id,s.nombre,e.last_sync_at,e.pendientes,coalesce(v.total_vendido,0) AS total_vendido,
            coalesce(v.ventas_count,0) AS ventas_count,coalesce(p.productos_count,0) AS productos_count,
            coalesce(p.alertas_stock,0) AS alertas_stock,coalesce(c.cierres_count,0) AS cierres_count,
            coalesce(c.diferencias,0) AS diferencias
        FROM public.sucursales s LEFT JOIN public.sucursales_estado e ON e.sucursal_id=s.id
        LEFT JOIN sales v ON v.sucursal_id=s.id LEFT JOIN products p ON p.sucursal_id=s.id
        LEFT JOIN cash c ON c.sucursal_id=s.id WHERE p_sucursal_id IS NULL OR s.id=p_sucursal_id
        ORDER BY s.nombre,s.id
    ) SELECT jsonb_build_object('branches',coalesce(jsonb_agg(to_jsonb(b)),'[]'::jsonb),
        'totals',jsonb_build_object('total_vendido',coalesce(sum(total_vendido),0),
            'ventas_count',coalesce(sum(ventas_count),0),'productos_count',coalesce(sum(productos_count),0),
            'alertas_stock',coalesce(sum(alertas_stock),0),'cierres_count',coalesce(sum(cierres_count),0),
            'diferencias',coalesce(sum(diferencias),0)),'fetched_at',now()) INTO result FROM branches b;
    RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION public.pagina_central(p_kind text,p_sucursal_id uuid DEFAULT NULL,
    p_fecha_desde date DEFAULT NULL,p_fecha_hasta date DEFAULT NULL,p_page integer DEFAULT 0,p_page_size integer DEFAULT 100)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
DECLARE table_name text; date_column text; from_time timestamptz; until_time timestamptz; items jsonb;
BEGIN
    IF NOT iss_private.is_admin() THEN RAISE EXCEPTION 'Se requiere administrador' USING ERRCODE='42501'; END IF;
    IF p_page IS NULL OR p_page<0 OR p_page>1000000 OR p_page_size IS NULL OR p_page_size<1 OR p_page_size>100 OR p_fecha_desde>p_fecha_hasta THEN
        RAISE EXCEPTION 'Paginación o fechas inválidas'; END IF;
    CASE p_kind WHEN 'productos' THEN table_name:='productos_sucursal';date_column:='synced_at';
        WHEN 'ventas' THEN table_name:='ventas_sucursal';date_column:='fecha';
        WHEN 'cierres' THEN table_name:='cierres_caja';date_column:='fecha_cierre';
        WHEN 'comandos' THEN table_name:='comandos_precios';date_column:='created_at';
        ELSE RAISE EXCEPTION 'Tipo de consulta inválido'; END CASE;
    from_time:=p_fecha_desde::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires';
    until_time:=(p_fecha_hasta+1)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires';
    -- Inventario representa la última instantánea, no movimientos entre fechas.
    IF p_kind='productos' THEN from_time:=NULL; until_time:=NULL; END IF;
    -- Identificadores proceden exclusivamente de la lista cerrada anterior.
    EXECUTE format('SELECT coalesce(jsonb_agg(to_jsonb(t)),''[]''::jsonb) FROM (
        SELECT r.*,s.nombre AS sucursal_nombre FROM public.%I r JOIN public.sucursales s ON s.id=r.sucursal_id
        WHERE ($1 IS NULL OR r.sucursal_id=$1)
          AND ($2 IS NULL OR r.%I >= $2) AND ($3 IS NULL OR r.%I < $3)
        ORDER BY r.%I DESC,r.sucursal_id,r.id LIMIT $4 OFFSET $5) t',table_name,date_column,date_column,date_column)
        INTO items USING p_sucursal_id,from_time,until_time,p_page_size+1,p_page::bigint*p_page_size;
    RETURN jsonb_build_object('rows',CASE WHEN jsonb_array_length(items)>p_page_size THEN items-p_page_size ELSE items END,
        'has_more',jsonb_array_length(items)>p_page_size);
END;
$$;

REVOKE ALL ON FUNCTION public.sincronizar_entidades(jsonb,bigint) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.solicitar_cambio_precios(uuid,uuid,bigint,numeric,numeric) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.confirmar_comandos_precios(jsonb) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.resumen_central(uuid,date,date) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.pagina_central(text,uuid,date,date,integer,integer) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.sincronizar_entidades(jsonb,bigint),public.confirmar_comandos_precios(jsonb),
    public.solicitar_cambio_precios(uuid,uuid,bigint,numeric,numeric),public.resumen_central(uuid,date,date),
    public.pagina_central(text,uuid,date,date,integer,integer) TO authenticated;
NOTIFY pgrst, 'reload schema';
COMMIT;
