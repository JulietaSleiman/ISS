-- Antes: Authentication > Users > Add user, crear con Auto Confirm User activado:
-- caja1.estacion-de-simoca@usuarios.invalid
-- La contraseña se introduce solo en ese panel; no se incluye en SQL o Git.
-- El dominio .invalid es técnico: no recibe correo. El administrador restablece claves.
BEGIN;
DO $$
DECLARE
    account_id uuid;
BEGIN
    SELECT id INTO account_id FROM auth.users
    WHERE lower(email) = 'caja1.estacion-de-simoca@usuarios.invalid';
    IF account_id IS NULL THEN
        RAISE EXCEPTION 'Primero cree caja1.estacion-de-simoca@usuarios.invalid en Authentication > Users con Auto Confirm User.';
    END IF;
    IF EXISTS (SELECT 1 FROM public.profiles WHERE id = account_id
               AND (sucursal_id <> 'f2985c88-2a4e-4e73-92d5-85d905b3db41' OR username <> 'caja1')) THEN
        RAISE EXCEPTION 'La cuenta ya tiene otra asignación. Revísela manualmente; no se reemplazará.';
    END IF;
    INSERT INTO public.profiles(id, username, sucursal_id, nombre, rol, activo)
    VALUES (account_id, 'caja1', 'f2985c88-2a4e-4e73-92d5-85d905b3db41', 'caja1', 'cajero', true)
    ON CONFLICT (id) DO NOTHING;
END;
$$;
COMMIT;
