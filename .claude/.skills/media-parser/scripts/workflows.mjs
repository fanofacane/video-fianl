import { open, unlink } from 'node:fs/promises';
import { resolve } from 'node:path';
import { setTimeout as sleep } from 'node:timers/promises';
import { callApi, ClientError } from './client.mjs';

// One in-memory cookie jar per workflow; never write credentials to disk/stdout.
export function sessionFetch(fetcher = fetch) {
  const cookies = new Map();
  let origin;
  return async (url, options = {}) => {
    const current = new URL(url).origin;
    if (origin && current !== origin) throw new Error('Session origin changed');
    origin = current;
    const response = await fetcher(url, {...options, headers: {...options.headers,
      ...(cookies.size ? {Cookie: [...cookies].map(([k,v])=>`${k}=${v}`).join('; ')} : {})}, redirect:'error'});
    for (const value of response.headers.getSetCookie()) {
      const pair=value.split(';',1)[0], split=pair.indexOf('=');
      if(split>0) cookies.set(pair.slice(0,split),pair.slice(split+1));
    }
    return response;
  };
}

export async function transcribe(config, text, waitSeconds = 600, fetcher = fetch, pollMs = 2000) {
  const request=sessionFetch(fetcher), jobs=[];
  const parsed=await callApi(config,'/api/parse',{text},request);
  const data=parsed.data, capability=data?.transcription;
  if(!capability?.enabled) throw new ClientError('TRANSCRIPTION_DISABLED','服务尚未启用口播转写');
  if(!capability.sources?.length || !capability.token) throw new ClientError('NO_TRANSCRIBABLE_VIDEO','没有可转写的视频；纯图片和纯音乐暂不支持口播转写');
  if(capability.ready===false) throw new ClientError('WORKER_UNAVAILABLE','转写服务正在准备，请稍后重试');
  try {
    const created=await callApi(config,'/api/transcriptions',{token:capability.token},request);
    if(!Array.isArray(created.data?.jobs) || !created.data.jobs.length) throw new ClientError('INVALID_RESPONSE','服务未返回转写任务');
    jobs.push(...created.data.jobs);
    const deadline=Date.now()+waitSeconds*1000;
    while(jobs.some(j=>!['completed','failed'].includes(j.state))) {
      if(Date.now()>=deadline) {
        const error=new ClientError('TRANSCRIPTION_TIMEOUT','等待转写超时，已结束本次等待；未完成内容不能当作完整文案');
        error.payload.jobs=jobs.map(publicJob);throw error;
      }
      for(let i=0;i<jobs.length;i++) {
        if(['completed','failed'].includes(jobs[i].state)) continue;
        const result=await callApi({...config,timeout:Math.max(.001,Math.min(config.timeout,(deadline-Date.now())/1000))},'/api/transcriptions/'+encodeURIComponent(jobs[i].id),undefined,request);
        jobs[i]=result.data;
      }
      if(jobs.some(j=>!['completed','failed'].includes(j.state))) await sleep(Math.min(pollMs,Math.max(0,deadline-Date.now())));
    }
    if(jobs.some(j=>j.state==='failed')) {
      const error=new ClientError('TRANSCRIPTION_FAILED','部分或全部视频转写失败，请查看 jobs 中的真实错误');
      error.payload.jobs=jobs.map(publicJob);throw error;
    }
    return {succ:true,data:{title:data.title,platform:data.platform,jobs:jobs.map(publicJob)}};
  } finally {
    // Copies of completed text are already in the result. Remove remote temporary jobs.
    for(const job of jobs) {
      try {await callApi({...config,timeout:10},'/api/transcriptions/'+encodeURIComponent(job.id),undefined,
        (url,opts)=>request(url,{...opts,method:'DELETE'}));} catch { /* Server TTL remains the fallback. */ }
    }
  }
}
function publicJob(job) {
  return {label:job.title || job.label,state:job.state,stage:job.stage,progress:job.progress,
          ...(job.state==='completed'?{text:job.text || '',segments:job.segments || [],duration:job.duration,model:job.model}:{}),...(job.error?{error:job.error,error_code:job.error_code}:{})};
}

export async function download(config,text,{kind,index,output},fetcher=fetch) {
  const request=sessionFetch(fetcher);
  const parsed=await callApi(config,'/api/parse',{text},request), manifest=parsed.data?.downloads;
  const items=manifest?.items || [], all=kind==='images';
  const item=items.find(i=>i.kind===kind && (index===undefined || i.index===index));
  if(!manifest?.token || (all?!items.some(i=>i.kind==='image'):!item)) throw new ClientError('RESOURCE_NOT_FOUND','这条内容没有指定类型或索引的资源');
  const path=resolve(output);let file;
  try {file=await open(path,'wx');} catch {throw new ClientError('OUTPUT_ERROR','无法创建输出文件：父目录需存在，且不得覆盖已有文件');}
  try {
    const response=await request(config.baseUrl+'/api/downloads',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({token:manifest.token,...(all?{all_images:true}:{index:item.index})}),signal:AbortSignal.timeout(config.timeout*1000)});
    if(!response.ok) {
      let failure={};try{failure=await response.json();}catch{}
      throw new ClientError(failure.error_code || `HTTP_${response.status}`,failure.retdesc || '下载失败',response.status);
    }
    const type=response.headers.get('content-type') || '';
    if(!/^(audio\/|video\/|image\/|application\/(zip|octet-stream))/.test(type)) throw new ClientError('INVALID_MEDIA','服务未返回媒体文件');
    let bytes=0;
    for await(const chunk of response.body) {
      bytes+=chunk.length;
      if(bytes>512*1024*1024) throw new ClientError('DOWNLOAD_TOO_LARGE','文件超过客户端 512 MB 上限');
      await file.writeFile(chunk);
    }
    if(!bytes) throw new ClientError('EMPTY_DOWNLOAD','服务返回空文件');
    return {succ:true,data:{path,bytes,content_type:type,kind,title:parsed.data.title}};
  } catch(error) {
    await file.close();file=null;await unlink(path);
    if(error instanceof ClientError) throw error;
    throw new ClientError('DOWNLOAD_FAILED','媒体下载中断，未保留不完整文件');
  } finally {await file?.close();}
}
