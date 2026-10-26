import base64
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/image_gen.py'
spec = importlib.util.spec_from_file_location('project_imagegen', SCRIPT)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class ImagegenTests(unittest.TestCase):
    def run_cli(self, *args, cwd=None):
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), *args], cwd=cwd,
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_default_flare_and_project_env_from_other_cwd(self):
        with tempfile.TemporaryDirectory() as folder:
            payload = self.run_cli('generate', '--prompt', 'Test', '--dry-run', cwd=folder)
        self.assertEqual(payload['model'], 'gpt-image-2.5-flare')
        self.assertEqual(payload['quality'], 'auto')
        self.assertEqual(payload['background'], 'auto')
        self.assertNotIn('api_key', payload)

    def test_native_transparency_and_high_quality(self):
        for quality in ('xhigh', 'max'):
            payload = self.run_cli('generate', '--prompt', 'Fox', '--quality', quality,
                                   '--size', '1536x864', '--background', 'transparent', '--dry-run')
            self.assertEqual(payload['quality'], quality)
            self.assertEqual(payload['background'], 'transparent')
            self.assertEqual(payload['output_format'], 'png')

    def test_invalid_combinations_fail_locally(self):
        checks = [lambda: client._validate_transparency('transparent', 'jpeg'),
                  lambda: client._validate_size('1920x1080', client.DEFAULT_MODEL),
                  lambda: client._validate_model('gpt-image-1.5'),
                  lambda: client._validate_model_specific_options(model=client.DEFAULT_MODEL, background='auto', input_fidelity='high'),
                  lambda: client._validate_generate_payload({'prompt': 'a', 'output_compression': 50, 'output_format': 'png'})]
        for check in checks:
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                check()

    def test_edit_and_batch_use_same_flare_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            from PIL import Image
            image = folder / 'source.png'
            Image.new('RGBA', (16, 16), (255, 0, 0, 0)).save(image)
            payload = self.run_cli('edit', '--image', str(image), '--prompt', 'Keep shape',
                                   '--quality', 'max', '--background', 'transparent', '--dry-run')
            self.assertEqual(payload['image'], [str(image)])
            self.assertNotIn('input_fidelity', payload)
            jobs = folder / 'jobs.jsonl'
            jobs.write_text(json.dumps({'prompt': 'bird', 'quality': 'xhigh', 'background': 'transparent'}), encoding='utf-8')
            payload = self.run_cli('generate-batch', '--input', str(jobs), '--out-dir', str(folder / 'out'), '--dry-run')
            self.assertEqual(payload['model'], client.DEFAULT_MODEL)
            self.assertEqual(payload['quality'], 'xhigh')

    def test_mock_generation_decodes_real_png(self):
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGBA', (16, 16), (255, 0, 0, 0)).save(buf, format='PNG')
        encoded = base64.b64encode(buf.getvalue()).decode()
        api = types.SimpleNamespace(images=types.SimpleNamespace(generate=lambda **kwargs: types.SimpleNamespace(data=[types.SimpleNamespace(b64_json=encoded)])))
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'image.png'
            with patch.object(sys, 'argv', [str(SCRIPT), 'generate', '--prompt', 'Fox', '--out', str(output), '--background', 'transparent']), patch.object(client, '_create_client', return_value=api), patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(client.main(), 0)
            with Image.open(output) as image:
                self.assertEqual(image.getchannel('A').getextrema(), (0, 0))

    def test_sdk_retries_disabled(self):
        with patch.dict(sys.modules, {'openai': types.SimpleNamespace(OpenAI=lambda **kwargs: kwargs, AsyncOpenAI=lambda **kwargs: kwargs)}):
            self.assertEqual(client._create_client()['max_retries'], 0)
            self.assertEqual(client._create_async_client()['max_retries'], 0)


if __name__ == '__main__':
    unittest.main()
