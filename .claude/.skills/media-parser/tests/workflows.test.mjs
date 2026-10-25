import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { transcribe, download } from '../scripts/workflows.mjs';
const config={baseUrl:'https://parser.example',timeout:2};
const json=(data,status=200,headers={})=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json',...headers}});
function mockWorkflow({failed=false,noVideo=false}={}) {
 const calls=[];
 const fetcher=async(url,options)=>{
  calls.push([url,options]);
  if(url.endsWith('/api/parse'))return json({succ:true,data:{title:'作品标题不是口播',platform:'测试',transcription:{enabled:true,ready:true,sources:noVideo?[]:[{index:0}],token:'private-token'}}},200,{'Set-Cookie':'session=secret; HttpOnly; Path=/'});
  assert.equal(options.headers.Cookie,'session=secret');
  if(options.method==='DELETE')return json({succ:true,data:{}});
  if(url.endsWith('/api/transcriptions'))return json({succ:true,data:{jobs:[{id:'j1',state:'queued'}]}},202);
  return json({succ:true,data:{id:'j1',title:'视频 1',state:failed?'failed':'completed',text:'完整口播内容',segments:[{start:0,text:'完整口播内容'}],error:failed?'音轨不可用':null,error_code:failed?'NO_AUDIO':null}});
 };
 return {fetcher,calls};
}
test('transcription keeps session, returns actual speech, cleans up and omits tokens',async()=>{
 const {fetcher,calls}=mockWorkflow();const result=await transcribe(config,'链接',2,fetcher,1);
 assert.equal(result.data.jobs[0].text,'完整口播内容');assert.equal(result.data.jobs[0].segments.length,1);
 assert.equal(calls.at(-1)[1].method,'DELETE');assert.ok(!JSON.stringify(result).includes('private-token'));
});
test('failed jobs return errors instead of titles and are cleaned up',async()=>{
 const {fetcher,calls}=mockWorkflow({failed:true});
 await assert.rejects(transcribe(config,'链接',2,fetcher,1),e=>e.payload.error_code==='TRANSCRIPTION_FAILED'&&e.payload.jobs[0].error_code==='NO_AUDIO');
 assert.equal(calls.at(-1)[1].method,'DELETE');
});
test('pure image or music does not enqueue speech',async()=>{
 const {fetcher,calls}=mockWorkflow({noVideo:true});await assert.rejects(transcribe(config,'链接',2,fetcher),e=>e.payload.error_code==='NO_TRANSCRIBABLE_VIDEO');assert.equal(calls.length,1);
});
test('waiting deadline cleans up and does not claim complete transcript',async()=>{
 const {fetcher,calls}=mockWorkflow();
 const wrapped=async(url,opts)=>url.endsWith('/j1')&&opts.method==='GET'?json({succ:true,data:{id:'j1',state:'running'}}):fetcher(url,opts);
 await assert.rejects(transcribe(config,'链接',.01,wrapped,1),e=>e.payload.error_code==='TRANSCRIPTION_TIMEOUT');assert.equal(calls.at(-1)[1].method,'DELETE');
});
test('audio and ordered image ZIP use session proxy, never overwrite output',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'media-skill-'));
 try{
  for(const kind of ['audio','images']){
   const output=join(dir,kind);const bytes=kind==='audio'?'ID3-test':'PK-test';
   const fetcher=async(url,opts)=>{
    if(url.endsWith('/parse'))return json({succ:true,data:{downloads:{token:'token',items:[{kind:'audio',index:2},{kind:'image',index:3}]}}},200,{'Set-Cookie':'session=s; Path=/'});
    assert.equal(opts.headers.Cookie,'session=s');const body=JSON.parse(opts.body);assert.deepEqual(body,kind==='audio'?{token:'token',index:2}:{token:'token',all_images:true});
    return new Response(bytes,{headers:{'Content-Type':kind==='audio'?'audio/mpeg':'application/zip'}});
   };
   const result=await download(config,'链接',{kind,output},fetcher);assert.equal(await readFile(output,'utf8'),bytes);assert.equal(result.data.bytes,bytes.length);
   await assert.rejects(download(config,'链接',{kind,output},fetcher),e=>e.payload.error_code==='OUTPUT_ERROR');
  }
 }finally{await rm(dir,{recursive:true,force:true});}
});
test('failed download removes incomplete file',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'media-skill-')),output=join(dir,'file');
 try{
  const fetcher=async(url)=>url.endsWith('/parse')?json({succ:true,data:{downloads:{token:'t',items:[{kind:'video',index:0}]}}}):json({succ:false,retdesc:'expired'},400);
  await assert.rejects(download(config,'链接',{kind:'video',output},fetcher),e=>e.payload.http_status===400);await assert.rejects(readFile(output));
 }finally{await rm(dir,{recursive:true,force:true});}
});
