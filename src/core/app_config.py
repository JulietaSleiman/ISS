"""Public installation settings. Administrative credentials never belong here."""
import os

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://zhodbzfqkezwjtvktyit.supabase.co').rstrip('/')
SUPABASE_PUBLISHABLE_KEY = os.environ.get(
    'SUPABASE_PUBLISHABLE_KEY', 'sb_publishable_LPyMs_9KdlhAxgb2A0Pizw_2zuZA8sZ')
# LEGACY: pistas de compatibilidad para recuperar instalaciones antiguas que ya
# tengan una vinculación real verificada. No son valores predeterminados para una
# PC nueva ni una fuente de autorización; el perfil y la sucursal vienen del servidor.
BRANCH_ID = os.environ.get('ISS_BRANCH_ID', 'f2985c88-2a4e-4e73-92d5-85d905b3db41')
BRANCH_NAME = os.environ.get('ISS_BRANCH_NAME', 'Estación de Simoca')
BRANCH_CODE = os.environ.get('ISS_BRANCH_CODE', 'estacion-de-simoca')
OFFLINE_DAYS = 30
