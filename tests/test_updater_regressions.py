import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.core import updater


class UpdaterRegressions(unittest.TestCase):
    def test_checker_uses_iss_release_and_selects_matching_executable(self):
        download_url = 'https://github.com/JulietaSleiman/ISS/releases/download/v1.1.1/SistemaIvanLlorens.exe'
        release = {
            'tag_name': 'v1.1.1', 'body': 'Correcciones',
            'assets': [
                {'name': 'OtraAplicacion.exe', 'browser_download_url': 'https://example.invalid/otro.exe', 'size': 100},
                {'name': 'SistemaIvanLlorens.exe', 'browser_download_url': download_url, 'size': 200},
            ],
        }
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = json.dumps(release).encode('utf-8')
        checker = updater.UpdateCheckerThread()
        received, errors = [], []
        checker.update_available.connect(received.append)
        checker.error_occurred.connect(errors.append)
        with patch.object(updater, 'CURRENT_VERSION', '1.1.0'), \
                patch.object(sys, 'frozen', True, create=True), \
                patch.object(sys, 'executable', str(Path('SistemaIvanLlorens.exe').resolve())), \
                patch.object(updater.urllib.request, 'urlopen', return_value=response) as request:
            checker.run()
        self.assertEqual(errors, [])
        self.assertEqual(request.call_args.args[0].full_url,
                         'https://api.github.com/repos/JulietaSleiman/ISS/releases/latest')
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]['download_url'], download_url)
        self.assertEqual(received[0]['version'], '1.1.1')
        self.assertEqual(received[0]['size'], 200)

    def test_failed_helper_launch_keeps_application_running(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            with patch.object(sys, 'frozen', True, create=True), \
                    patch.object(sys, 'executable', str(Path(directory) / 'app.exe')), \
                    patch('tempfile.gettempdir', return_value=directory), \
                    patch.object(updater.subprocess, 'Popen', side_effect=OSError('denied')), \
                    patch.object(updater.QMessageBox, 'warning') as warning, \
                    patch.object(updater.QApplication, 'quit') as quit_app, \
                    patch.object(updater.os, '_exit') as exit_process:
                self.assertFalse(updater.apply_update_and_restart('download.exe'))
                warning.assert_called_once()
                quit_app.assert_not_called()
                exit_process.assert_not_called()

    def test_generated_helper_preserves_dependencies_and_uses_atomic_replace(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            with patch.object(sys, 'frozen', True, create=True), \
                    patch.object(sys, 'executable', str(Path(directory) / 'app.exe')), \
                    patch('tempfile.gettempdir', return_value=directory), \
                    patch.object(updater.subprocess, 'Popen') as launch, \
                    patch.object(updater.QApplication, 'quit'), \
                    patch.object(updater.os, '_exit', side_effect=SystemExit):
                with self.assertRaises(SystemExit):
                    updater.apply_update_and_restart(str(Path(directory) / 'download.exe'))
                script = Path(directory, 'update_bebidasfrias.ps1').read_text(encoding='utf-8-sig')
                self.assertIn('[System.IO.File]::Replace($stagedExe, $currentExe, $backupExe)', script)
                self.assertNotIn('Remove-Item -LiteralPath $internalDir', script)
                self.assertNotIn('-Recurse', script)
                launch.assert_called_once()
                self.assertIn('Hidden', launch.call_args.args[0])
                self.assertEqual(launch.call_args.kwargs['env']['PYINSTALLER_RESET_ENVIRONMENT'], '1')
            if os.name == 'nt':
                # Parse the generated helper without executing its update/delete commands.
                result = subprocess.run([
                    'powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                    "$errors = $null; $tokens = $null; "
                    "[System.Management.Automation.Language.Parser]::ParseInput("
                    "[Console]::In.ReadToEnd(), [ref]$tokens, [ref]$errors) > $null; "
                    "if ($errors.Count) { $errors | Out-String | Write-Output; exit 1 }"
                ], input=script,
                    text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
