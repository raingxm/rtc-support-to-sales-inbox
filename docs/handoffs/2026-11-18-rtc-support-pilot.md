# RTC 技术支持试点交接

2026-11-18。换电脑后，从这份文档继续 `grill-with-docs` 的下一轮。

## 工作上下文

- [GitHub #6](https://github.com/raingxm/rtc-support-to-sales-inbox/issues/6) 是现有规格，覆盖客户会话、厂商公开文档引用、人工接手和商机。后续消息留在同一张工单上的第一张票 [#7](https://github.com/raingxm/rtc-support-to-sales-inbox/issues/7) 已关闭，由 [PR #8](https://github.com/raingxm/rtc-support-to-sales-inbox/pull/8) 合入。
- [Upwork 招聘帖](https://www.upwork.com/jobs/~022115739208598410375) 是需求参考。已通过 Upwork MCP 读取招聘正文。帖子把异步文档入库、带引用的混合检索、低信心转人工、运营可见性、身份权限和模型输入脱敏列为产品要求。另发给入围者的技术规格未取得。
- 已确认的待办和接手定义见 [CONTEXT.md](../../CONTEXT.md)。找不到可核对的公开文档依据时，工单进入待人工处理。支持人员发出本轮第一条客户可见的人工回复时正式接手。商机仍由人员单独确认，参见 #6。停止等待之后的迟到结果见 [ADR 0011](../adr/0011-a-late-quoted-reply-publishes-only-before-a-person-takes-over.md)。
- 词汇表里的「回复」是客户已经看得见的消息，系统或支持人员都可以发出。「草稿」还没进会话。ADR 0001–0010 已在 `docs/adr/`。ADR 0003、0005、0006 保持：没点名厂商用 TRTC；写下 LiveKit 仍先澄清；确认是 LiveKit 公司后才用它的公开文档。

## 开源对标

| 项目 | 借鉴点 |
| --- | --- |
| [Chatwoot](https://github.com/chatwoot/chatwoot) | 作为主要对标。参考[机器人转人工与交还](https://www.chatwoot.com/hc/user-guide/articles/1677497472-how-to-use-agent-bots)和[身份验证](https://www.chatwoot.com/hc/user-guide/articles/1782283175-understanding-contact-identity-and-identity-validation-in-chatwoot)。[故障报告 #15835](https://github.com/chatwoot/chatwoot/issues/15835) 提供一个验收场景：文档索引积压时，客户消息仍须进入可处理的人工待办。 |
| [Zammad](https://github.com/zammad/zammad) | 参考[工单详情与历史](https://user-docs.zammad.org/en/latest/basics/zammad-ui.html)。支持人员需要知道工单为何进入待办、等了多久、谁接手、谁确认或撤销商机。 |
| [RAGFlow](https://github.com/infiniflow/ragflow) | 参考[检索测试](https://github.com/infiniflow/ragflow/blob/main/docs/quickstart.mdx)。先选 RTC 错误码、SDK 版本和中英文问法作为测试题，标出预期的厂商官方页面，再比较关键词与混合检索。分别检查文档是否可检索、预期段落是否命中、答案是否引用该段落。 |

## 已复现的差距

- 模拟模型分析失败后，新工单及未确认交接工单的补充消息均未保存。建议先持久化客户原话，再分析。验收时模拟超时，刷新客户和支持入口，核对原话、工单号、待办原因和等待时长。[工单模块](../../api/inbox.py)
- 在本地隔离的内存环境中，无身份 API 请求能列出工单、读会话和确认交接。试点应验收客户只能读写自己的工单、技术支持可以处理待办和确认商机，以及客户接口只返回客户可见内容。[API 路由](../../api/main.py)
- 模型适配器目前发送客户会话全文。用虚构的 `UserSig` 和 `SDKSecretKey` 检查实际模型请求中的脱敏结果，同时核对排障需要的错误码、SDK 版本和发生时间仍可用。[模型适配器](../../api/model_analyzer.py) · [TRTC 凭证文档](https://trtc.io/document/34385)

## 已定

1. **试点服务谁。** 一家厂商的一支支持团队。客户入口和支持入口分开。先验收三件事：客户只能读写自己的工单、客户原话先落库再分析、进入待人工处理之后支持人员能在同一张工单上看到原因并回复。多租户、自助注册、嵌入组件、n8n 通知先不排。曾考虑把试点收成 LiveKit，已收回。
2. **停止等待之后才到达的模型结果。** 见 ADR 0011。停止等待时不发回复。接手前、带文档原句的结果发成回复。没有文档原句的不发。人工接手之后留作草稿。交还不发布这份草稿。客户入口不显示待人工处理。

3. **客户怎样再进入自己的工单。** 先不建客户账号。客户用这张工单的地址回到客户入口，阅读回复并继续说话。客户只能打开自己持有地址的那张工单。支持入口里，这支团队的每名支持人员都能看到全部工单。
4. **低信心。** 试点不设。等待时限内返回且带文档原句的，发成回复。进入待人工处理只有两种原因：没有打开的公开文档，或已经停止等待、客户还没有看到带文档原句的回复。
5. **人工接手不记名。** 任何一名支持人员发出本轮第一条客户可见回复，工单进入人工接手。这支团队的任何支持人员都可以继续回复或交还。
6. **一个地址一张工单。** 客户入口不提供工单列表。
7. **模型脱敏。** `UserSig`、`SDKSecretKey` 这类凭证不进入模型请求。错误码、SDK 版本和发生时间留下。
8. **两个入口怎么进。** 见 ADR 0012。支持人员要登录。客户靠工单地址，只知道工单号打不开客户入口。
9. **更新的客户原话。** 客户又发来一条消息后，针对更早会话的迟到结果丢掉，不留作草稿，也不进入会话。系统改等包含最新一条客户消息的结果。会话没变且已经人工接手时，迟到结果仍留作草稿。
10. **各自登录。** 每名支持人员一个登录。撤销记录记下是谁撤销的。
11. **等待时长。** 从客户最后一次开口算起。系统的「答不了」不清零。
12. **署名。** 见 ADR 0013。支持人员发出的回复两边都带这名支持人员的名字。确认商机、撤销、交还都在支持入口记下是谁做的。人工接手这个状态本身不记名。系统发出的回复不署支持人员的名字。
13. **过时分流。** 和过时回复一起丢掉。尚未确认的分流保持到包含最新一句的分析到达；还没有分流时先空着。确认商机不因为分流还没更新而被拦住，依据仍是客户原话。
14. **旧草稿。** 人工接手期间留下的草稿，客户又开口后丢掉，包括已经改过、还没发出的。不换成一份新草稿。支持人员按最新的客户原话自己写。分析仍可更新尚未确认的分流。人工接手期间的那条客户消息，交还后也不补发成回复。

## 还没定

无。共同理解已写入 [GitHub #6](https://github.com/raingxm/rtc-support-to-sales-inbox/issues/6)。五张票已发布：[#9](https://github.com/raingxm/rtc-support-to-sales-inbox/issues/9)、[#10](https://github.com/raingxm/rtc-support-to-sales-inbox/issues/10) 可以开始；[#11](https://github.com/raingxm/rtc-support-to-sales-inbox/issues/11) 和 [#12](https://github.com/raingxm/rtc-support-to-sales-inbox/issues/12) 受 #9 挡住；[#13](https://github.com/raingxm/rtc-support-to-sales-inbox/issues/13) 受 #11 挡住。

## 建议使用的技能

- 五张票已发布。可以开始的是 #9 和 #10。
