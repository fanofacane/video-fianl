# 参考库与成品库

**做任何一期视频之前，必须先读 [docs/hooks.md](../docs/hooks.md) 和 [docs/body-writing.md](../docs/body-writing.md)，再读完 `reference/` 下与本期话题最接近的 2 个对标视频的 `meta.md`、`breakdown.md`、`frames.jpg`（中版有逐秒帧 `frames_1s_p*.jpg`，优先参考）。**

## reference/ 对标视频（按视频分类）

| 目录 | 作者 | 发布标题 | 时长 | 类型 | 概念 |
| --- | --- | --- | --- | --- | --- |
| [jdl-renge-duli](reference/jdl-renge-duli/) | 江东陵 | 人格越独立 爱就越单纯 付出者 富有 珍重 | 185s | 长版 | 内在动机 |
| [jdl-guanxi-zhiliang](reference/jdl-guanxi-zhiliang/) | 江东陵 | 人其实需要的不是形式，而是关系的质量。 | 202s | 长版 | 情感回应 |
| [jdl-qiwu-mimang](reference/jdl-qiwu-mimang/) | 江东陵 | 早上会起雾，所以迷茫是很正常的 | 218s | 长版 | 原因论 |
| [jdl-yanchi-manzu](reference/jdl-yanchi-manzu/) | 江东陵 | 为什么聪明的人，都在延迟吗满足？ | 197s | 长版 | 延迟满足 |
| [jdl-paolu-jineng](reference/jdl-paolu-jineng/) | 江东陵 | 跑路是人这一生最重要的技能 | 113s | 中版 | 认知解离（逐秒拆解） |
| [jdl-renzhi-bihe](reference/jdl-renzhi-bihe/) | 江东陵 | 共勉 | 136s | 中版 | 认知闭合（逐秒拆解） |
| [deyi-shiyong-fouding](reference/deyi-shiyong-fouding/) | 得一. | 不要允许任何人一边使用你一边否定你的价值 | 116s | 中版 | 认知失调（逐秒拆解） |
| [deyi-xingfu-xuanxiang](reference/deyi-xingfu-xuanxiang/) | 得一. | 幸福的人不是拥有最多选项的人，而是那些能对大部分选项说“我不需要”的人 | 120s | 中版 | 选择悖论（逐秒拆解） |
| [jdl-shijie-kaochang](reference/jdl-shijie-kaochang/) | 江东陵 | 世界不是一个审判你的考场，更多时候，它只是一个人来人往的广场。 | 131s | 中版 | 焦点效应（聚光灯效应同题） |
| [deyi-zhenxin-zunzhong](reference/deyi-zhenxin-zunzhong/) | 得一. | 你的真心待人为什么总是不被尊重？ | 68s | 短版 | 破窗效应 |
| [deyi-rensheng-rongcuolv](reference/deyi-rensheng-rongcuolv/) | 得一. | 为什么曾以为天大的事后来却提都懒得提？ | 64s | 短版 | 人生容错率 |
| [jdl-jieshou-wenti](reference/jdl-jieshou-wenti/) | 江东陵 | 人生很多问题不是用来解决的，而是用来接受的 | 156s | 长版 | 强迫性思维 |
| [jdl-xingwei-daan](reference/jdl-xingwei-daan/) | 江东陵 | 行为就是答案，接受就继续，不接受就离开 | 173s | 长版 | 行动化 |
| [jdl-chilai-aishang](reference/jdl-chilai-aishang/) | 江东陵 | 接住迟来的哀伤，人生才算真正开始愈合 | 185s | 长版 | 迟发性哀伤 |
| [deyi-shengming-changdu](reference/deyi-shengming-changdu/) | 得一. | 生命的长度，足以稀释错误的浓度，生命的广度，也会淡化那些让你耿耿于怀的记忆 | 128s | 中版 | 斯多葛学派（视角翻篇） |
| [deyi-zhishi-zuzhou](reference/deyi-zhishi-zuzhou/) | 得一. | 知识诅咒：知道的越多，就很难回到无知的状态 | 113s | 中版 | 知识诅咒 |

每个目录：
- `meta.md`：发布标题、简介（都是“标题 + 话题”）、话题、时长、字数、语速、链接
- `frames.jpg`：场景帧截图（每 3 秒一帧），看画面元素、构图和节奏
- `breakdown.md`：文案结构拆解（段落作用、手法、标题写法、可学之处）
- `transcript.txt`：完整转写稿（语音自动转写，未校对；部分尚未生成）

完整转写稿入库：
- **[four_transcripts.md](four_transcripts.md)：4 个对标视频的口播全文，写逐字稿前必须逐篇仔细阅读，学它们的文笔**（句子节奏、口语说法、转折、比喻落地、收尾）。
- 其余对标的转写稿在各自目录的 `transcript.txt`；没有的运行 `python3 -m video.library ref <slug> <链接>` 生成并提交。写稿时可以直接引用、化用其中合适的句子。

新增对标视频：`python3 -m video.library ref <slug> <分享链接>`，然后手写 `breakdown.md`，并在上表加一行。

## ours/ 我们的成品（按发布标题分类）

| 目录 | 概念 | 时长 | 日期 |
| --- | --- | --- | --- |
| [为什么关系越近，越容易互相伤害？](ours/为什么关系越近，越容易互相伤害？/) | 刺猬法则 | 71s | 2026-10-25 |
| [极度自卑的人，其实也是极度自信的人](ours/极度自卑的人，其实也是极度自信的人/) | 聚光灯效应 | 85s | 2026-10-25 |
| [为什么你越真心待人，越得不到对方的尊重呢？](ours/为什么你越真心待人，越得不到对方的尊重呢？/) | 边际效用 | 108s | 2026-10-26 |
| [很多成长不是一点一点发生的，而是在某一天突然发生的](ours/很多成长不是一点一点发生的，而是在某一天突然发生的/) | 高原现象 | 98s | 2026-10-27 |
| [你所厌恶的现在，是未来的你回不到的曾经](ours/你所厌恶的现在，是未来的你回不到的曾经/) | 心智游移（活在当下） | 94s | 2026-10-27 |

每期成片后运行 `python3 -m video.library ours episodes/<slug>/episode.json` 归档（封面、场景帧、逐字稿、发布标题与简介），并在上表加一行。
