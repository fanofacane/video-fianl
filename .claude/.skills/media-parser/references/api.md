# 接口与维护

默认服务 `https://media.agentcore.top`。当前线上技能只读挂载路径为 `/data/workbench/platform/pi-extensions/skills/media-parser`，宿主机目录 `/opt/fan-agent/platform/pi-agent/skills/media-parser`。以实际技能加载器提供的 location 为准；不依赖固定工作目录。

## 能力与接口

| 方法和路径 | 用途 |
| --- | --- |
| POST /api/parse | `{text:分享链接或分享文本}`；返回资源、下载清单与转写能力 |
| POST /api/downloads | 同会话 `{token,index}` 下载单项，或 `{token,all_images:true}` 下载整组 ZIP |
| POST /api/transcriptions | 同会话 `{token:transcription.token}` 创建任务，返回 202 与 data.jobs |
| GET /api/transcriptions/{id} | 同会话查看 state、stage、progress、text、segments、error_code、error |
| DELETE /api/transcriptions/{id} | 同会话删除临时任务 |
| GET /api/transcriptions/{id}/text | 已完成任务的纯文本；CLI 直接使用任务 JSON 全文 |
| GET /api/health | 连通性检查，不表示所有来源或转写 worker 正常 |
| GET /api/platforms | 已注册平台名单，不是每条链接均可解析的保证 |
| GET /api/openapi.json | 服务公开 API schema；转写/下载的实际请求如上 |

`data.title/desc/author` 是作品元数据；`video_url/video_list/image_list/cover_url/audio_url` 是来源媒体；`downloads.items` 为 `{index,kind,url}` 清单；`transcription` 包含 enabled、ready、sources 与短期 token。

## 会话和结果

解析会设置匿名会话 Cookie，下载令牌与转写令牌都绑定该会话，通常有效一小时。Node fetch 不会自动保存 Cookie，所以 workflows.mjs 为每次工作流维护独立内存 Cookie jar；重定向被拒绝，不能把凭证转发到其他来源。不要手工拼接上次 parse 的令牌启动另一个进程。

`transcribe` 在一个进程里解析、提交所有视频任务、轮询并返回真实口播。任何任务失败，整体退出码为 1，stderr.jobs 保留已完成文本及失败原因；超时不把局部结果当全文。完成后或异常路径尽力 DELETE 已知任务；无法送达时依赖服务器 TTL。强制杀进程不会保证立即清理。

当前后端 POST 创建接口会提交该作品的全部转写 sources，不支持 CLI 单独选择某条视频转写；最多 16 条。纯图片 OCR、纯音乐转歌词、本地文件上传没有接入，不作承诺。

`download` 使用服务器签名清单代理下载，写入调用环境指定路径，不生成公共文件 URL。保存时采用独占创建，禁止覆盖已有文件，网络错误会删除已创建的不完整文件。保留平台返回的内容类型，不做格式转码。整组图片 ZIP 按来源顺序打包。

预览卡片通过 present_media 的 sourceUrl 自行建立工作台会话，不能使用 CLI Cookie 或令牌。只需要口播文字时直接调用 transcribe，不依赖 present_media 是否可用。

## 错误处理

- 分享文案无链接/过长：修正输入。
- 会员、Cookie、删除、私密或来源验证限制：按真实错误说明，不自动绕过或重复提交。
- WORKER_UNAVAILABLE/TRANSCRIPTION_DISABLED：转写尚未就绪，不当作解析失败。
- NO_TRANSCRIBABLE_VIDEO：没有视频音轨来源，不能用标题冒充口播。
- TRANSCRIPTION_TIMEOUT：等待到期，当前调用尝试清理任务，明确返回未完成情况。
- 网络错误：只读操作可重试一次；创建任务结果不确定时不盲目重新创建。

## 验证

在技能目录运行：

```sh
node --test tests/client.test.mjs tests/workflows.test.mjs
node scripts/client.mjs health
```

单元与受控 HTTP 测试覆盖跨工作目录执行、中文 stdin、配置覆盖、错误 JSON、同 Cookie 会话、完成与失败清理、超时、无视频来源、音频和 ZIP 下载以及防覆盖。真实线上验证应使用获授权的公开分享链接；不要输出 Cookie、下载令牌或转写令牌。
