-- Crear ANTES la cuenta en Authentication > Users > Add user, con Auto Confirm.
-- Correo técnico: administracion.estacion-de-simoca@usuarios.invalid
-- Definir la contraseña fuera del chat. Esta cuenta es distinta de caja1.
BEGIN;
DO $$
DECLARE user_id uuid;
BEGIN
    SELECT id INTO user_id FROM auth.users WHERE lower(email)='administracion.estacion-de-simoca@usuarios.invalid';
    IF user_id IS NULL THEN RAISE EXCEPTION 'Primero cree la cuenta administracion en Authentication > Users'; END IF;
    IF EXISTS (SELECT 1 FROM public.profiles p WHERE p.id=user_id AND
        (p.username IS DISTINCT FROM 'administracion' OR
         p.sucursal_id IS DISTINCT FROM 'f2985c88-2a4e-4e73-92d5-85d905b3db41'::uuid OR p.rol IS DISTINCT FROM 'admin')) THEN
        RAISE EXCEPTION 'El perfil existente tiene otra identidad, sucursal o rol. Revise su asignación; no se modificará automáticamente';
    END IF;
    INSERT INTO public.profiles(id,username,sucursal_id,nombre,rol,activo)
        VALUES(user_id,'administracion','f2985c88-2a4e-4e73-92d5-85d905b3db41','Administración central','admin',true)
        ON CONFLICT(id) DO NOTHING; -- No reactiva una cuenta deshabilitada al repetir el script.
END;
$$;
COMMIT;
