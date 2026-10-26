import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from video import episode, review


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / 'sample'
        self.ep = {'name': 'sample', 'title': '标题', 'lines': [{'zh': '第一句。'}, {'zh': '第二句。'}],
                   'opening': {'lines': 1, 'background': {}}, 'assets': {}, 'scenes': [], 'publish': {}}
        self.path = self.root / 'episode.json'
        self.save()
        self.settings = {'voice_id': 'testVoice', 'model': 'speech-2.8-hd', 'base_url': 'https://api.minimax.cn/v1',
                         'speed': 1, 'vol': 1, 'pitch': 0}
        for target, value in [('OUTPUT', self.root)]:
            patcher = patch.object(episode, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(review, 'voice_settings', return_value=self.settings)
        patcher.start()
        self.addCleanup(patcher.stop)

    def save(self):
        self.path.write_text(json.dumps(self.ep), encoding='utf-8')

    def approve_script(self):
        revision = review.script_id(self.ep)
        review.approve(self.work, 'script', revision, revision)

    def voice(self):
        self.approve_script()
        folder, audio, receipt = review.voice_paths(self.ep, self.work, self.settings)
        folder.mkdir(parents=True, exist_ok=True)
        audio.write_bytes(b'fake audio')
        review.write_json(receipt, {'voice_id': review.voice_id(self.ep, self.settings),
                                    'audio_sha256': review.file_digest(audio)})
        return folder, audio

    def test_unapproved_voice_shots_and_final_have_no_side_effects(self):
        with patch.object(episode.subprocess, 'run') as run:
            for action in [lambda: episode.generate_voice(self.ep, self.work),
                           lambda: episode.build(self.path, shots=True), lambda: episode.build(self.path)]:
                with self.assertRaisesRegex(ValueError, '尚未确认'):
                    action()
            run.assert_not_called()
        self.assertFalse(self.work.exists())

    def test_approval_does_not_synthesize_and_rejects_stale_id(self):
        old = review.script_id(self.ep)
        self.ep['lines'][0]['zh'] = '修改稿。'
        with self.assertRaises(ValueError):
            review.approve(self.work, 'script', old, review.script_id(self.ep))
        with patch.object(episode.subprocess, 'run') as run:
            self.approve_script()
            run.assert_not_called()
        self.assertFalse(episode.status(self.ep, self.work)['voice_ready'])

    def test_shots_never_synthesize_missing_voice(self):
        self.approve_script()
        with patch.object(episode.subprocess, 'run') as run, self.assertRaisesRegex(ValueError, '--voice'):
            episode.build(self.path, shots=True)
        run.assert_not_called()

    def test_explicit_voice_generates_once_and_reuses(self):
        self.approve_script()
        def fake_tts(command, **kwargs):
            Path(command[command.index('--output') + 1]).write_bytes(b'new audio')
        with patch.object(episode.subprocess, 'run', side_effect=fake_tts) as run, patch.object(episode, '_audio_len', return_value=3):
            first = episode.generate_voice(self.ep, self.work)
            second = episode.generate_voice(self.ep, self.work)
            self.assertEqual(first, second)
            self.assertEqual(run.call_count, 1)

    def test_changed_script_invalidates_approval_and_preserves_old_audio(self):
        _, old = self.voice()
        self.ep['lines'][0]['zh'] = '新文案。'
        with self.assertRaisesRegex(ValueError, '尚未确认'):
            episode.generate_voice(self.ep, self.work)
        self.approve_script()
        with self.assertRaisesRegex(ValueError, '没有已完成配音'):
            review.require_voice(self.ep, self.work, self.settings)
        self.assertEqual(old.read_bytes(), b'fake audio')

    def test_failed_paid_request_is_not_retried(self):
        self.approve_script()
        with patch.object(episode.subprocess, 'run', side_effect=RuntimeError('timeout')) as run:
            with self.assertRaises(RuntimeError):
                episode.generate_voice(self.ep, self.work)
            with self.assertRaisesRegex(ValueError, '禁止自动重试'):
                episode.generate_voice(self.ep, self.work)
            self.assertEqual(run.call_count, 1)

    def test_voice_setting_change_and_audio_tamper_block_reuse(self):
        _, audio = self.voice()
        changed = {**self.settings, 'voice_id': 'anotherVoice'}
        with self.assertRaises(ValueError):
            review.require_voice(self.ep, self.work, changed)
        audio.write_bytes(b'replacement')
        with self.assertRaisesRegex(ValueError, '不符'):
            review.require_voice(self.ep, self.work, self.settings)

    def test_visual_review_requires_current_preview_and_assets(self):
        _, audio = self.voice()
        preview = self.root / 'shots.jpg'
        preview.write_bytes(b'preview')
        revision = review.visual_id(self.ep, self.work, audio)
        review.write_json(self.work / 'reviews/shots-produced.json',
                          {'revision': revision, 'preview': str(preview), 'preview_sha256': review.file_digest(preview)})
        with self.assertRaisesRegex(ValueError, '截图尚未确认'):
            episode.build(self.path)
        review.approve(self.work, 'shots', revision, review.shots_revision(self.ep, self.work, self.settings))
        self.assertTrue(episode.status(self.ep, self.work)['shots_approved'])
        assets = self.work / 'assets'
        assets.mkdir()
        (assets / 'new.png').write_bytes(b'new asset')
        with self.assertRaisesRegex(ValueError, '已变化'):
            review.shots_revision(self.ep, self.work, self.settings)

    def test_line_split_gets_new_alignment_without_new_voice(self):
        folder, audio = self.voice()
        original_id = review.voice_id(self.ep, self.settings)
        self.ep['lines'] = [{'zh': '第一句。第二句。'}]
        self.approve_script()
        self.assertEqual(review.voice_id(self.ep, self.settings), original_id)
        align = types.SimpleNamespace(char_times=lambda p: [], align_lines=lambda *args: [[0, 3]])
        with patch.dict('sys.modules', {'video.align': align}), patch.object(episode, '_audio_len', return_value=3), patch.object(episode.subprocess, 'run') as run:
            result = episode.narration(self.ep, self.work)
            self.assertEqual(result[2], [[0, 3]])
            run.assert_not_called()

    def test_preview_approval_allows_render_and_regeneration_requires_review(self):
        _, audio = self.voice()
        preview = self.root / 'shots.jpg'
        preview.write_bytes(b'preview')
        from unittest.mock import Mock
        body = Mock(return_value=preview)
        opening = Mock(return_value=self.root / 'opening.mp4')
        modules = {'video.body.build': types.SimpleNamespace(build=body),
                   'video.opening.build': types.SimpleNamespace(build=opening)}
        with patch.dict('sys.modules', modules), \
                patch.object(episode, 'narration', return_value=(audio, 3, [[0, 1], [1, 3]])), \
                patch.object(episode, 'plan', return_value=({}, {}, 1)), \
                patch.object(episode.subprocess, 'run') as run:
            self.assertEqual(episode.build(self.path, shots=True), preview)
            run.assert_not_called()
            revision = review.shots_revision(self.ep, self.work, self.settings)
            review.approve(self.work, 'shots', revision, revision)
            self.assertEqual(episode.build(self.path), self.work / 'final.mp4')
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][0], 'ffmpeg')
            preview.write_bytes(b'changed preview')
            with self.assertRaisesRegex(ValueError, '已变化'):
                episode.build(self.path)
            episode.build(self.path, shots=True)
            with self.assertRaisesRegex(ValueError, '截图尚未确认'):
                episode.build(self.path)


if __name__ == '__main__':
    unittest.main()
