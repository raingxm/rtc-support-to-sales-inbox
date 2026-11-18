# RTC 技术支持试点交接

2026-11-18。换电脑后，从这份文档继续 `grill-with-docs` 的下一轮。

## 工作上下文

- [GitHub #6](https://github.com/raingxm/rtc-support-to-sales-inbox/issues/6) 是现有规格，覆盖客户会话、厂商公开文档引用、人工接手和商机。后续消息留在同一张工单上的第一张票 [#7](https://github.com/raingxm/rtc-support-to-sales-inbox/issues/7) 已关闭，由 [PR #8](https://github.com/raingxm/rtc-support-to-sales-inbox/pull/8) 合入。
- [Upwork 招聘帖](https://www.upwork.com/jobs/~022115739208598410375) 是需求参考。已通过 Upwork MCP 读取招聘正文。帖子把异步文档入库、带引用的混合检索、低信心转人工、运营可见性、身份权限和模型输入脱敏列为产品要求。另发给入围者的技术规格未取得。
- 已确认的待办和接手定义见 [CONTEXT.md](../../CONTEXT.md)。找不到可核对的公开文档依据时，工单进入待人工处理。技术支持发出本轮第一条客户可见的人工回复时正式接手。商机仍由人员单独确认，参见 #6。
- #6 允许系统直接回复，当前词汇表里的「回复」由技术支持发出。下一轮要对齐「系统回复」「人工回复」「草稿」。#6 引用的 ADR 0001–0010 上一轮在本地检出中未找到，找到原文后再对照。

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

## 等用户决定

1. **试点服务谁？** 建议按一家 RTC 厂商的一支技术支持团队验收，保留独立的客户入口和支持入口，优先做工单权限、可靠收件和人工待办。多租户、自助注册、嵌入组件和 n8n 通知等试点需要后再排。
2. **待人工处理期间如何处置迟到的 AI 回复？** 检索超时后，工单已进入人工待办，模型随后返回一条有出处的答案。建议从进入人工待办起暂停自动发布，直到技术支持交还系统。请确认这条规则，并在实现时覆盖迟到的结果。

## 建议使用的技能

- `grill-with-docs` 调用 `grilling` 和 `domain-modeling`。先确认上述两项，更新已定术语，再讨论依赖这些决定的问题。
- `to-spec` 和 `to-tickets`。规则定下来后，先核对并更新 #6，再拆出端到端的第一张票。建议从「客户消息已保存 → 模型超时 → 技术支持在同一张工单看到原因并回复」开始。
