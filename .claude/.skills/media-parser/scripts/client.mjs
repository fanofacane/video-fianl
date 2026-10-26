#!/usr/bin/env node
import { readFile, stat } from 'node:fs/promises';
import { parseArgs } from 'node:util';
import { pathToFileURL } from 'node:url';

export class ClientError extends Error {
  constructor(code, message, status, exitCode = 1) {
    super(message);
    this.payload = { succ: false, error_code: code, retdesc: message };
    if (status !== undefined) this.payload.http_status = status;
    this.exitCode = exitCode;
  }
}

export async function loadConfig(values = {}, env = process.env) {
  const defaults = JSON.parse(await readFile(new URL('../service.json', import.meta.url), 'utf8'));
  const raw = values['base-url'] || env.MEDIA_PARSER_BASE_URL || defaults.baseUrl;
  let url;
  try { url = new URL(raw); } catch { throw new ClientError('INVALID_BASE_URL', '解析服务地址必须是 HTTP(S) URL'); }
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new ClientError('INVALID_BASE_URL', '服务地址不能包含账号、查询参数或片段');
  }
  const timeout = Number(values.timeout ?? defaults.timeoutSeconds);
  if (!Number.isFinite(timeout) || timeout <= 0 || timeout > 600) throw new ClientError('INVALID_TIMEOUT', '超时必须大于 0 且不超过 600 秒');
  return { baseUrl: url.href.replace(/\/$/, ''), timeout };
}

export async function callApi(config, route, body, fetcher = fetch) {
  let response, text;
  try {
    response = await fetcher(config.baseUrl + route, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(Math.ceil(config.timeout * 1000)),
      redirect: 'error',
    });
    text = await response.text();
  } catch (error) {
    const timeout = ['TimeoutError', 'AbortError'].includes(error.name);
    throw new ClientError(timeout ? 'TIMEOUT' : 'NETWORK_ERROR', timeout ? '解析请求超时，请稍后重试' : '无法连接解析服务，请检查服务地址、网络和服务状态');
  }
  let payload;
  try { payload = JSON.parse(text); } catch {
    throw new ClientError(response.ok ? 'INVALID_RESPONSE' : `HTTP_${response.status}`, response.ok ? '服务未返回有效 JSON' : `接口返回 HTTP ${response.status}`, response.status);
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new ClientError('INVALID_RESPONSE', '接口应返回 JSON 对象', response.status);
  if (!response.ok || payload.succ === false) {
    throw new ClientError(payload.error_code || `HTTP_${response.status}`, payload.retdesc || '解析失败', response.status);
  }
  return payload;
}

async function inputText(values) {
  const sources = [values.url !== undefined, values['input-file'] !== undefined, values.stdin === true].filter(Boolean).length;
  if (sources !== 1) throw new ClientError('USAGE_ERROR', '此命令必须且只能选择 --url、--input-file 或 --stdin', undefined, 2);
  let text = values.url;
  if (values['input-file']) {
    try {
      if ((await stat(values['input-file'])).size > 16000) throw new ClientError('INVALID_TEXT', '分享文本不能超过 2000 字符');
      text = await readFile(values['input-file'], 'utf8');
    } catch (error) {
      if (error instanceof ClientError) throw error;
      throw new ClientError('INPUT_FILE_ERROR', '无法读取指定的 UTF-8 分享文本文件');
    }
  }
  if (values.stdin) {
    process.stdin.setEncoding('utf8'); text = '';
    for await (const chunk of process.stdin) {
      text += chunk;
      if (text.length > 4000) throw new ClientError('INVALID_TEXT', '分享文本不能超过 2000 字符');
    }
  }
  text = (text || '').replace(/^\uFEFF/, '').trim();
  if (!text || Array.from(text).length > 2000) throw new ClientError('INVALID_TEXT', '分享文本必须为 1–2000 个字符');
  return text;
}

export async function main(argv = process.argv.slice(2)) {
  try {
    let parsed;
    try {
      parsed = parseArgs({ args: argv, allowPositionals: true, options: {
        url: { type: 'string' }, 'input-file': { type: 'string' }, stdin: { type: 'boolean' },
        'wait-seconds': {type:'string'}, kind:{type:'string'}, index:{type:'string'}, output:{type:'string'},
        'base-url': { type: 'string' }, timeout: { type: 'string' }, help: { type: 'boolean' },
      } });
    } catch { throw new ClientError('USAGE_ERROR', '参数无效，使用 --help 查看命令', undefined, 2); }
    const { values, positionals } = parsed;
    if (values.help) {
      console.log('node scripts/client.mjs <parse|transcribe|download|health|platforms|schema> [--base-url URL] [--timeout 110]\nparse/transcribe/download: --url TEXT | --input-file UTF8_FILE | --stdin\ntranscribe: --wait-seconds 600（最大 3600）；download: --kind video|audio|cover|image|images --output FILE [--index 清单索引]\n默认服务器来自技能目录 service.json，可用 MEDIA_PARSER_BASE_URL 覆盖。');
      return 0;
    }
    const routes = { parse: '/api/parse', health: '/api/health', platforms: '/api/platforms', schema: '/api/openapi.json', transcribe:null, download:null };
    const command = positionals[0];
    if (positionals.length !== 1 || !Object.hasOwn(routes, command)) throw new ClientError('USAGE_ERROR', '命令应为 parse、transcribe、download、health、platforms 或 schema', undefined, 2);
    if (!['parse','transcribe','download'].includes(command) && (values.url !== undefined || values['input-file'] !== undefined || values.stdin)) throw new ClientError('USAGE_ERROR', '分享文本参数只用于 parse/transcribe/download', undefined, 2);
    const config = await loadConfig(values);
    if((command!=='transcribe' && values['wait-seconds']!==undefined) || (command!=='download' && ['kind','index','output'].some(k=>values[k]!==undefined))) throw new ClientError('USAGE_ERROR','选项不适用于当前命令',undefined,2);
    let payload;
    if(command==='transcribe') {
      const wait=Number(values['wait-seconds'] ?? 600);
      if(!Number.isFinite(wait)||wait<1||wait>3600)throw new ClientError('USAGE_ERROR','等待时间必须为 1–3600 秒',undefined,2);
      const {transcribe}=await import('./workflows.mjs');
      payload=await transcribe(config,await inputText(values),wait);
    } else if(command==='download') {
      const index=values.index===undefined?undefined:Number(values.index);
      if(!['video','audio','cover','image','images'].includes(values.kind)||!values.output||(index!==undefined&&(!Number.isInteger(index)||index<0))||(values.kind==='images'&&index!==undefined))throw new ClientError('USAGE_ERROR','下载需指定有效 --kind 与 --output；--index 是清单索引，整组图片不接受索引',undefined,2);
      const {download}=await import('./workflows.mjs');
      payload=await download(config,await inputText(values),{kind:values.kind,index,output:values.output});
    } else {
      const body = command === 'parse' ? { text: await inputText(values) } : undefined;
      payload = await callApi(config, routes[command], body);
    }
    console.log(JSON.stringify(payload, null, 2));
    return 0;
  } catch (error) {
    const failure = error instanceof ClientError ? error : new ClientError('CLIENT_ERROR', '客户端配置或执行异常，请检查技能文件是否完整');
    console.error(JSON.stringify(failure.payload));
    return failure.exitCode;
  }
}

// 不用顶层 await：workflows.mjs 会反向 import 本文件，顶层 await 会让两者互相等待而退出（exit 13）。
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main().then((code) => { process.exitCode = code; });
