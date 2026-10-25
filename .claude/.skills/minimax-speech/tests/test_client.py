import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('speech_client', Path(__file__).resolve().parents[1] / 'scripts/client.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class SpeechTests(unittest.TestCase):
    def args(self, *extra):
        return client.parser().parse_args(['tts', '--text', '你好(laughs)', '--output', 'test.mp3', '--voice-id', 'testVoice', *extra])

    def test_payload_preserves_text_and_voice(self):
        args = self.args('--speed', '1.2', '--emotion', 'happy')
        payload = client.tts_payload(args)
        self.assertEqual(payload['text'], '你好(laughs)')
        self.assertEqual(payload['voice_setting']['voice_id'], 'testVoice')
        self.assertEqual(payload['voice_setting']['speed'], 1.2)
        self.assertEqual(payload['output_format'], 'hex')
        self.assertFalse(payload['stream'])

    def test_errors_and_incomplete_audio_are_not_success(self):
        for response in [{'base_resp': {'status_code': 1008}},
                         {'base_resp': {'status_code': 0}, 'data': None},
                         {'base_resp': {'status_code': 0}, 'data': {'status': 1, 'audio': '494433'}},
                         {'base_resp': {'status_code': 0}, 'data': {'status': 2, 'audio': 'nothex'}}]:
            with self.assertRaises(ValueError):
                client.decode_audio(response)

    def test_invalid_options_fail_before_request(self):
        for extra in [('--speed', '3'), ('--vol', '0'), ('--pitch', '13'), ('--speed', 'nan')]:
            with self.assertRaises(ValueError):
                client.tts_payload(self.args(*extra))

    def test_output_is_decoded_and_never_overwritten(self):
        result = {'base_resp': {'status_code': 0}, 'data': {'status': 2, 'audio': '494433'}, 'trace_id': 'test'}
        with tempfile.TemporaryDirectory() as folder:
            args = self.args('--output', str(Path(folder) / 'voice.mp3'))
            with patch.object(client, 'post', return_value=result) as post:
                client.synthesize(args, 'https://api.minimax.cn/v1', 'private-key')
                self.assertEqual(Path(args.output).read_bytes(), b'ID3')
                meta = Path(args.output + '.json').read_text(encoding='utf-8')
                self.assertNotIn('private-key', meta)
                self.assertNotIn('494433', meta)
                with self.assertRaises(ValueError):
                    client.synthesize(args, 'https://api.minimax.cn/v1', 'private-key')
                self.assertEqual(post.call_count, 1)

    def test_clone_reuses_file_id_without_upload(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'new'
            args = client.parser().parse_args(['clone', '--file-id', '123', '--voice-id', 'newVoice01', '--output-dir', str(out)])
            with patch.object(client, 'post', return_value={'base_resp': {'status_code': 0}}) as post:
                result = client.clone(args, 'https://api.minimax.cn/v1', 'private-key')
                self.assertEqual(result['file_id'], 123)
                self.assertEqual(post.call_args.args[2], '/voice_clone')
                self.assertEqual(post.call_count, 1)
                self.assertEqual(json.loads((out / 'request.json').read_text())['voice_id'], 'newVoice01')


if __name__ == '__main__':
    unittest.main()
