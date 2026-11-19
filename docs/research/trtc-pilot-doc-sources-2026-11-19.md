# TRTC 参考试点的文档来源与验收题

2026-11-19。为 [TRTC 首批官方文档和验收题从哪里取](https://github.com/raingxm/rtc-support-to-sales-inbox/issues/22) 核对腾讯 RTC 的公开文档、页面原文和 HTTP 响应。

## 获取官方文档

- 从 RTC Engine 产品索引挑页。产品索引列出共用的服务端能力文档，并链接到 Web、Android、iOS、Flutter 等平台索引。Web 索引直接列出 SDK 快速开始和 API 概览的 Markdown 链接。全站索引和 sitemap 可辅助发现页面，索引摘要用于挑页，文档正文用于核对文档原句。 [官方说明](https://trtc.io/document/77713) · [全站索引](https://trtc.io/llms.txt) · [RTC Engine 索引](https://trtc.io/llms/rtc-engine.txt) · [Web 索引](https://trtc.io/llms/rtc-engine/web.txt) · [站点地图](https://trtc.io/sitemap.xml)
- 试点可从人工确认的文档列表抓取官方 Markdown，记录产品、平台、适用版本、实际正文语言和官方阅读页。抽样中，Web 进房指南、原生错误码、App 发布日志和云端录制概览的中英文 Markdown 都返回 HTTP 200。创建录制 API 的英文 Markdown 可用，中文 Markdown 返回 404，对应中文路径的 HTML 仍显示英文 API 正文。遇到这种情况，可检查英文原文是否能支持答案，然后按客户语言写说明，保留引文语言。 [Web 进房英文 Markdown](https://trtc.io/document/48424.md) · [Web 进房中文 Markdown](https://trtc.io/zh/document/48424.md) · [创建录制 API 英文 Markdown](https://trtc.io/document/46960.md) · [创建录制 API 中文路径](https://trtc.io/zh/document/46960)
- 引用优先指向 HTML 的 `canonical` 阅读地址。HTML 的 `hreflang` 可以找对应语言，正文仍需核对。Web 进房第二节的英文锚点是 `#step-2`，中文是 `#step2`，录制页还有带编码和 UUID 的锚点。抽样只能说明这些锚点目前有效。入库时保存章节路径，可以在页面锚点核对通过时给出直达链接，其余情况引用页面地址。实际引用的文字以公开阅读页可核对的正文为准，遇到原句无法匹配时走既有无依据规则。 [英文进房第二节](https://trtc.io/document/48424#step-2) · [中文进房第二节](https://trtc.io/zh/document/48424#step2) · [云端录制](https://trtc.io/document/45169) · [文档原句规则](../adr/0004-capability-reply-quotes-one-open-page.md)
- RTC Engine 索引和抽测的 Web 指南 Markdown 带 `ETag` 和 `Last-Modified`，用原 `ETag` 发送 `If-None-Match` 得到 304。Web 指南的 HTML 与 Markdown 返回的 `Last-Modified` 日期不同。试点可用条件请求减少重复下载，以提取出的正文变化决定是否重建索引。版本以正文标注和发布日志为准。例如中文版与英文版 App 发布日志对 13.4 发布日分别写 2026 年 7 月 6 日与 8 日，遇到精确日期问题应保留来源差异。 [RTC Engine 索引](https://trtc.io/llms/rtc-engine.txt) · [Web 指南 Markdown](https://trtc.io/document/48424.md) · [Web 指南阅读页](https://trtc.io/document/48424) · [中文 App 发布日志](https://trtc.io/zh/document/39426) · [英文 App 发布日志](https://trtc.io/document/39426)

## 首批验收题

建议先覆盖 RTC Engine Web 进房、原生 SDK 的进房鉴权与错误码、App 发布日志、服务端云录制。这六题可以作为最小烟测集。扩大题集后，保留错误码和 API 名称精确匹配的题，再加入语义改写题，用同一份语料分别比较关键词与混合检索。检索单独记录是否找到正确页面和段落，回复单独检查来源是否支持结论、文档原句是否可核对、语言是否符合客户消息。

| 类别 | 模拟客户问题 | 预期依据和表现 |
| --- | --- | --- |
| 接入 | “我在 Web SDK 5.x 中已经拿到了 UserSig，进房时要传哪些参数？” | 定位 Web 版进房步骤和参数，依据 `trtc.enterRoom()` 的参数说明回答。保留 `sdkAppId`、`userId`、`userSig` 和房间标识的写法。 [Web 进房](https://trtc.io/zh/document/48424#step2) · [Web API 适用版本](https://trtc.io/zh/document/41664) |
| 错误码 | “Our native Android app gets `-3301` in `TRTCCloudListener.onError` right after entering. What does it mean?” | 命中原生 TRTC ErrorCode 的 `TXLiteAVError` 表，说明进房失败，结合回调的具体错误消息判断原因。腾讯 RTC 同站另一张通用表把同一码描述为网络访问受限，可当检索干扰项。 [原生错误码](https://trtc.io/document/40140#bb60aec5429af9dd69df09c23f924e96) · [同码干扰页](https://trtc.io/document/60027) |
| SDK 版本 | “TRTC App SDK 13.5 的 OHOS 能不能打开摄像头闪光灯？发布日志怎么写的？” | 找到 App 发布日志 13.5 小节的新特性，定位 OHOS 摄像头闪光灯，引用中文原文。 [App 发布日志](https://trtc.io/zh/document/39426) |
| 产品能力 | “Can TRTC save each subscribed participant separately instead of combining them into one recording?” | 找到云端录制的单流与混流说明。单流分别录制已订阅的流，混流合成一个结果。用同一页的原文支撑答复。 [云端录制单流章节](https://trtc.io/document/45169#.E5.8D.95.E6.B5.81.E5.BD.95.E5.88.B6) |
| 版本歧义 | “Web 上我这边写的是 `TRTC.createClient()`，同事给的代码是 `trtc.enterRoom()`，应该怎么进房？” | 识别两代 API，先确认 `package.json` 中的包名和版本，再给对应步骤。官方迁移指南可用来标注答案，其中 v4 是 `TRTC.createClient()` 与 `client.join()`，v5 是 `TRTC.create()` 与 `trtc.enterRoom()`。若首批语料只收 v5，确认是 v4 后走无适用依据的兜底。 [官方 v4 → v5 迁移指南](https://web.sdk.qcloud.com/trtc/webrtc/doc/en/tutorial-07-info-v4-to-v5-migration.html) · [TRTC Web v5 概览](https://trtc.io/document/41664) |
| 缺少依据 | “昨天晚上任务 `task-example-001` 的录制到底有没有上传成功？请直接给成功时间。” | 官方文档能解释录制事件和回调，无法查证这次模拟任务的实际结果。系统说明无法确认，原工单进入人工处理。运行验收时用模拟任务标识和回调记录。 [云端录制与录制事件](https://trtc.io/document/45169) · [无公开文档依据时的回复规则](../adr/0010-no-page-means-no-commercial-question.md) |

对 `UserSig` 排障可以加一条验收变体。客户在 `-100018` 消息里贴虚构的 `UserSig` 或 `SDKSecretKey` 时，现有的模型请求脱敏之后，检索仍能定位原生错误码的校验失败条目，客户不必再发送凭证。 [原生错误码](https://trtc.io/zh/document/40140) · [UserSig 生成文档](https://trtc.io/zh/document/34385) · [模型请求脱敏](https://github.com/raingxm/rtc-support-to-sales-inbox/issues/10)
