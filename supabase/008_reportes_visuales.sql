-- Ejecutar DESPUÉS de 004. Agrega gráficos al mismo resumen sin cambiar tablas.
-- Ventas y cierres: fechas inclusivas del negocio en Argentina (fin exclusivo UTC).
-- Inventario: última instantánea activa, independiente del filtro de fechas.
-- Serie: día <=62 días; semana <=366; mes <=3650; año para el resto.
-- Un rango de más de 500 años se rechaza: no se omiten ventas ni se etiquetan
-- grupos de varios años como si fueran un año. Como máximo, 500 puntos anuales.
BEGIN;

CREATE OR REPLACE FUNCTION public.resumen_central(p_sucursal_id uuid DEFAULT NULL,
    p_fecha_desde date DEFAULT NULL,p_fecha_hasta date DEFAULT NULL)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = '' AS $$
DECLARE
    result jsonb; from_time timestamptz; until_time timestamptz;
    first_sale date; last_sale date; trend_from date; trend_to date;
    business_today date := (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date;
    grain text; step_size interval; days_count integer;
BEGIN
    IF NOT iss_private.is_admin() THEN
        RAISE EXCEPTION 'Se requiere administrador' USING ERRCODE='42501';
    END IF;
    IF p_fecha_desde > p_fecha_hasta THEN RAISE EXCEPTION 'Rango de fechas inválido'; END IF;
    IF (p_fecha_desde IS NOT NULL AND (NOT isfinite(p_fecha_desde) OR extract(year FROM p_fecha_desde) NOT BETWEEN 1 AND 9999))
       OR (p_fecha_hasta IS NOT NULL AND (NOT isfinite(p_fecha_hasta) OR extract(year FROM p_fecha_hasta) NOT BETWEEN 1 AND 9999)) THEN
        RAISE EXCEPTION 'Las fechas deben pertenecer a los años 1 a 9999';
    END IF;
    from_time := p_fecha_desde::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires';
    until_time := (p_fecha_hasta+1)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires';

    SELECT min((fecha AT TIME ZONE 'America/Argentina/Buenos_Aires')::date),
           max((fecha AT TIME ZONE 'America/Argentina/Buenos_Aires')::date)
        INTO first_sale,last_sale FROM public.ventas_sucursal
        WHERE estado<>'CANCELADA' AND (p_sucursal_id IS NULL OR sucursal_id=p_sucursal_id)
          AND (from_time IS NULL OR fecha>=from_time) AND (until_time IS NULL OR fecha<until_time);
    trend_to := coalesce(p_fecha_hasta,last_sale,p_fecha_desde,business_today);
    trend_from := coalesce(p_fecha_desde,first_sale,greatest(date '0001-01-01',trend_to-29));
    days_count := trend_to-trend_from+1;
    IF extract(year FROM trend_from) NOT BETWEEN 1 AND 9999 OR extract(year FROM trend_to) NOT BETWEEN 1 AND 9999
       OR extract(year FROM trend_to)-extract(year FROM trend_from)+1 > 500 THEN
        RAISE EXCEPTION 'Seleccione un período de hasta 500 años para visualizar la evolución';
    END IF;
    IF days_count<=62 THEN grain:='day';step_size:=interval '1 day';
    ELSIF days_count<=366 THEN grain:='week';step_size:=interval '1 week';
    ELSIF days_count<=3650 THEN grain:='month';step_size:=interval '1 month';
    ELSE grain:='year';step_size:=interval '1 year'; END IF;

    WITH filtered_sales AS MATERIALIZED (
        SELECT * FROM public.ventas_sucursal WHERE estado<>'CANCELADA'
          AND (p_sucursal_id IS NULL OR sucursal_id=p_sucursal_id)
          AND (from_time IS NULL OR fecha>=from_time) AND (until_time IS NULL OR fecha<until_time)
    ), active_products AS MATERIALIZED (
        SELECT * FROM public.productos_sucursal WHERE activo
          AND (p_sucursal_id IS NULL OR sucursal_id=p_sucursal_id)
    ), filtered_cash AS MATERIALIZED (
        SELECT * FROM public.cierres_caja WHERE (p_sucursal_id IS NULL OR sucursal_id=p_sucursal_id)
          AND (from_time IS NULL OR fecha_cierre>=from_time) AND (until_time IS NULL OR fecha_cierre<until_time)
    ), sales AS (
        SELECT sucursal_id,count(*) AS ventas_count,coalesce(sum(total),0) AS total_vendido
        FROM filtered_sales GROUP BY sucursal_id
    ), products AS (
        SELECT sucursal_id,count(*) AS productos_count,
            count(*) FILTER(WHERE stock_actual<=stock_minimo) AS alertas_stock
        FROM active_products GROUP BY sucursal_id
    ), cash AS (
        SELECT sucursal_id,count(*) AS cierres_count,coalesce(sum(diferencia),0) AS diferencias
        FROM filtered_cash GROUP BY sucursal_id
    ), branches AS (
        SELECT s.id,s.nombre,e.last_sync_at,e.pendientes,coalesce(v.total_vendido,0) AS total_vendido,
            coalesce(v.ventas_count,0) AS ventas_count,coalesce(p.productos_count,0) AS productos_count,
            coalesce(p.alertas_stock,0) AS alertas_stock,coalesce(c.cierres_count,0) AS cierres_count,
            coalesce(c.diferencias,0) AS diferencias
        FROM public.sucursales s LEFT JOIN public.sucursales_estado e ON e.sucursal_id=s.id
        LEFT JOIN sales v ON v.sucursal_id=s.id LEFT JOIN products p ON p.sucursal_id=s.id
        LEFT JOIN cash c ON c.sucursal_id=s.id WHERE p_sucursal_id IS NULL OR s.id=p_sucursal_id
    ), branch_summary AS (
        SELECT coalesce(jsonb_agg(to_jsonb(b) ORDER BY nombre,id),'[]'::jsonb) AS branches,
            jsonb_build_object('total_vendido',coalesce(sum(total_vendido),0),
                'ventas_count',coalesce(sum(ventas_count),0),'productos_count',coalesce(sum(productos_count),0),
                'alertas_stock',coalesce(sum(alertas_stock),0),'cierres_count',coalesce(sum(cierres_count),0),
                'diferencias',coalesce(sum(diferencias),0)) AS totals FROM branches b
    ), bucketed_sales AS (
        SELECT date_trunc(grain,fecha AT TIME ZONE 'America/Argentina/Buenos_Aires')::date AS bucket,
            sum(total) AS total,count(*) AS count FROM filtered_sales GROUP BY 1
    ), series AS (
        SELECT generate_series(date_trunc(grain,trend_from::timestamp),
            date_trunc(grain,trend_to::timestamp),step_size)::date AS bucket
    ), trend AS (
        SELECT jsonb_build_object('granularity',grain,'points',coalesce(jsonb_agg(
            jsonb_build_object('date',to_char(s.bucket,'YYYY-MM-DD'),'total',coalesce(v.total,0),
                'count',coalesce(v.count,0)) ORDER BY s.bucket),'[]'::jsonb)) AS chart
        FROM series s LEFT JOIN bucketed_sales v ON v.bucket=s.bucket
    ), payment_groups AS (
        SELECT CASE metodo_pago WHEN 'EFECTIVO' THEN 'Efectivo'
            WHEN 'TRANSFERENCIA' THEN 'Transferencia' WHEN 'TARJETA/TRANSFERENCIA' THEN 'Tarjeta / transferencia'
            WHEN 'FIADO / CTA. CTE.' THEN 'Cuenta corriente' WHEN 'MIXTO' THEN 'Mixto'
            ELSE metodo_pago END AS label,sum(total) AS total,count(*) AS count
        FROM filtered_sales GROUP BY 1
    ), payments AS (
        SELECT coalesce(jsonb_agg(jsonb_build_object('label',label,'total',total,'count',count)
            ORDER BY total DESC,label),'[]'::jsonb) AS chart FROM payment_groups
    ), cash_health AS (
        SELECT jsonb_build_object('balanced_count',count(*) FILTER(WHERE diferencia=0),
            'shortage_count',count(*) FILTER(WHERE diferencia<0),'surplus_count',count(*) FILTER(WHERE diferencia>0),
            'shortage_total',coalesce(sum(greatest(-diferencia,0)),0),
            'surplus_total',coalesce(sum(greatest(diferencia,0)),0)) AS chart FROM filtered_cash
    ), stock_health AS (
        SELECT jsonb_build_object('healthy_count',count(*) FILTER(WHERE stock_actual>0 AND stock_actual>stock_minimo),
            'low_count',count(*) FILTER(WHERE stock_actual>0 AND stock_actual<=stock_minimo),
            'out_count',count(*) FILTER(WHERE stock_actual<=0)) AS chart FROM active_products
    ) SELECT jsonb_build_object('branches',b.branches,'totals',b.totals,'fetched_at',now(),
        'charts',jsonb_build_object('sales_trend',t.chart,'payment_methods',p.chart,
            'cash_closures',c.chart,'stock_health',s.chart)) INTO result
        FROM branch_summary b CROSS JOIN trend t CROSS JOIN payments p CROSS JOIN cash_health c CROSS JOIN stock_health s;
    RETURN result;
END;
$$;

REVOKE ALL ON FUNCTION public.resumen_central(uuid,date,date) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.resumen_central(uuid,date,date) TO authenticated;
NOTIFY pgrst, 'reload schema';
COMMIT;
