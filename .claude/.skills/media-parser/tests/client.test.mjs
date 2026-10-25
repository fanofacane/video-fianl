import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { callApi, loadConfig } from '../scripts/client.mjs';

test('server config is portable and explicit override wins', async () => {
  assert.equal((await loadConfig({}, {})).baseUrl, 'https://media.agentcore.top');
  assert.equal((await loadConfig({}, { MEDIA_PARSER_BASE_URL: 'https://parser.example' })).baseUrl, 'https://parser.example');
  assert.equal((await loadConfig({ 'base-url': 'https://explicit.example' }, { MEDIA_PARSER_BASE_URL: 'https://ignored.example' })).baseUrl, 'https://explicit.example');
  await assert.rejects(loadConfig({ 'base-url': 'file:///tmp/data' }), e => e.payload.error_code === 'INVALID_BASE_URL');
});

test('CLI works from a different cwd, preserves Chinese input and reports failures', async () => {
  const server = createServer(async (req, res) => {
    let body = ''; for await (const chunk of req) body += chunk;
    const data = JSON.parse(body || '{}');
    res.setHeader('Content-Type', 'application/json');
    if (data.text === '失败') { res.writeHead(400); res.end(JSON.stringify({ succ: false, error_code: 'URL_NOT_FOUND', retdesc: '未找到有效链接' })); return; }
    res.end(JSON.stringify({ succ: true, data: { title: data.text, video_url: 'https://example.com/video.mp4', image_list: [{ url: 'https://example.com/image.jpg' }] } }));
  });
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  const base = `http://127.0.0.1:${server.address().port}`;
  const run = (text, args = ['parse', '--stdin']) => new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [fileURLToPath(new URL('../scripts/client.mjs', import.meta.url)), ...args, '--base-url', base], { cwd: tmpdir() });
    let stdout = '', stderr = '';
    child.stdout.setEncoding('utf8').on('data', chunk => stdout += chunk);
    child.stderr.setEncoding('utf8').on('data', chunk => stderr += chunk);
    child.on('error', reject); child.on('close', code => resolve({ code, stdout, stderr }));
    child.stdin.end(text);
  });
  try {
    const text = '分享文案 https://example.com/?x=1&y=2\n引号"与$符号';
    const success = await run(text);
    assert.equal(success.code, 0); assert.equal(success.stderr, '');
    assert.equal(JSON.parse(success.stdout).data.title, text);
    assert.equal(JSON.parse(success.stdout).data.image_list.length, 1);
    const failed = await run('失败');
    assert.equal(failed.code, 1); assert.equal(failed.stdout, '');
    assert.equal(JSON.parse(failed.stderr).error_code, 'URL_NOT_FOUND');
    const oversized = await run('文'.repeat(2001));
    assert.equal(oversized.code, 1); assert.equal(JSON.parse(oversized.stderr).error_code, 'INVALID_TEXT');
    const missing = await run('', ['parse']); assert.equal(missing.code, 2);
  } finally { server.close(); await once(server, 'close'); }
});

test('non-JSON and connection failures produce stable errors', async () => {
  const config = { baseUrl: 'https://example.com', timeout: 2 };
  await assert.rejects(callApi(config, '/api/parse', {}, async () => new Response('<html>bad gateway</html>', { status: 502 })), e => e.payload.error_code === 'HTTP_502');
  await assert.rejects(callApi(config, '/api/parse', {}, async () => { throw new DOMException('timeout', 'TimeoutError'); }), e => e.payload.error_code === 'TIMEOUT');
  await assert.rejects(callApi(config, '/api/parse', {}, async () => { throw new Error('offline'); }), e => e.payload.error_code === 'NETWORK_ERROR');
});
