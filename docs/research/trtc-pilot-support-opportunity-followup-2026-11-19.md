# TRTC 参考试点的人工接手和商机跟进（2026-11-19）

本次核对厂商官方文档，并静态检查仓库在 `d569f42` 的入口。以下产品行为来自文档，试点场景是据此提出的验收建议。价格、真实账号和集成端到端行为留待实际接入时核对。

## 客服接手

**Chatwoot** 的 AgentBot 会把新会话放在 `pending`，接收会话事件并在同一会话回复。需要人处理时，机器人可以把会话改为 `open`。支持人员可将它改回 `pending`，交还机器人。可借鉴的是保留会话与明确交还动作。试点里的「待人工处理」和「人工接手」是自己的状态命名，接手发生在支持人员发出第一条回复时。 [Chatwoot AgentBot](https://www.chatwoot.com/hc/user-guide/articles/1677497472-how-to-use-agent-bots) · [试点规格](https://github.com/raingxm/rtc-support-to-sales-inbox/issues/6)

**Zammad** 的工单侧栏提供历史，可以查谁在什么时候做了什么。公开回复和默认仅内部可见的工单备注分开。多人打开同一张工单时，界面还显示谁在查看或编辑。试点可先核对已有的回复署名、交还和确认或撤销商机记录，判断是否能回溯关键操作，在线编辑提示是否有必要可由两人走查决定。 [Zammad 工单侧栏](https://user-docs.zammad.org/en/latest/basics/zammad-ui.html#sidebar) · [Zammad 工单操作](https://user-docs.zammad.org/en/latest/basics/work-with-tickets.html)

| 模拟工单 | 参考试点可观察结果 |
| --- | --- |
| 客户反馈 TRTC Android 入房失败。官方依据查不到，或模型超时。 | 原话先落到同一张工单。支持人员从队列找到它，在详情看到待人工原因及从客户最后一句开始的等待时间。客户继续用原地址补充信息。超时后客户入口无待人工状态，也没有未核对答复。 |
| 客户补充 SDK 版本。支持人员 A 先回复，B 继续跟进并交还。 | 客户看到两条署名回复。人工接手期间，系统不自动回复该时段的客户消息。旧会话的迟到结果不进会话。交还后原工单继续存在，支持人员能看到 B 的交还记录，系统只可能回应客户下一条消息。 |
| 同一张工单既有已确认商机，又因新技术问题进入待人工。 | 支持人员在队列能直接识别这张工单需要回复。解决方案工程师仍能继续跟进商机。这条值得优先走查。当前列表的徽标文字优先显示商机已确认或已撤销，待人工原因在详情才会再出现。 [工单队列与详情](https://github.com/raingxm/rtc-support-to-sales-inbox/blob/d569f422bf18a2d4b731dc9954897df3f613c323/web/app/page.tsx#L33-L70) |

前两条复用 [试点规格](https://github.com/raingxm/rtc-support-to-sales-inbox/issues/6) 和 [迟到结果 ADR](https://github.com/raingxm/rtc-support-to-sales-inbox/blob/main/docs/adr/0011-a-late-quoted-reply-publishes-only-before-a-person-takes-over.md)。Chatwoot 的 Captain 积压问题是用户报告，可用来构造「知识系统跌倒时仍有人接住」的故障场景，报告本身没有证明其频率或当前版本行为。 [Chatwoot 队列积压报告](https://github.com/chatwoot/chatwoot/issues/15835)

## 商机跟进的两条路径

### 仓内轻量跟进

**DevRev** 展示了同一产品里独立的商机对象和来源链接。用户在 Opportunities 建记录时填写负责人和账户，可以关联已有工单与会话。商机还带阶段等销售字段。该帮助页无法证实指派时会发什么通知，也没有描述从客服原话自动锁定证据或具体跟进任务的界面。**Gainsight** 则给出可移植的证据呈现方式。人在机会卡上看客户原话、参与者和日期，再选是否推进。其 Expansion Analyst 不会自动写 Salesforce。 [DevRev Opportunity](https://support.devrev.ai/en-US/devrev/article/VSU6Qz6K-opportunity) · [Gainsight Expansion Analyst](https://support.gainsight.com/Staircase_AI/Staircase_AI_Features/Expansion_Analyst)

**试点建议**是让登录的解决方案工程师能从自己的跟进列表找到已确认商机，打开授权的来源工单和客户原话，记录下一步和跟进结果。列表可先承担「交到了」的可见性，再决定是否需要主动提醒。现有商机模型保存的是负责人，支持端能确认或撤销。如果采用仓内路径，至少需要可验证的工程师身份、来源访问授权及跟进记录。现有规格把工程师入口和队列列在范围之外，这会是一项后续范围决定。确认仍由支持人员完成，跟进记录不进入客户会话。 [当前商机模型](https://github.com/raingxm/rtc-support-to-sales-inbox/blob/d569f422bf18a2d4b731dc9954897df3f613c323/api/inbox.py#L105-L108) · [试点规格](https://github.com/raingxm/rtc-support-to-sales-inbox/issues/6)

### 已有 CRM

**HubSpot** 的 Deal 和 Ticket 可以在侧栏新建或关联，关联可从两端查看。Deal 能指派给有对象查看权限及适用席位的 HubSpot 用户。跟进任务可指定用户、到期时间、提醒和备注，并关联 Deal。负责人可以完成任务，或在 Deal 时间线记录备注、会议和通话结果。HubSpot 也提供 Deal 指派与任务通知，送达受用户设置和指派方式影响。 [记录关联](https://knowledge.hubspot.com/records/associate-records) · [记录归属](https://knowledge.hubspot.com/records/how-to-set-a-record-owner) · [任务](https://knowledge.hubspot.com/tasks/create-tasks) · [完成任务](https://knowledge.hubspot.com/tasks/complete-tasks) · [跟进活动](https://knowledge.hubspot.com/records/manually-log-activities-on-records) · [通知](https://knowledge.hubspot.com/user-management/how-to-set-up-user-notifications-in-hubspot)

**试点建议**是等采用团队确定已有 CRM，再用一个手动交接样本核实负责人账号、通知、来源链接和结果记录。若后续自动写入，需决定负责人和外部记录 ID 如何映射、CRM 写入失败如何补交、重复确认或重试怎样避免重复建单、撤销怎样反映到外部记录。HubSpot 的对象关联以已有 CRM 记录为前提。若试点工单留在本仓库，需设计可授权访问的内部工单链接，或明确同步哪部分工单。客户工单地址持有即能访问，不适合作为 CRM 侧共享链接。文档核实了 Deal 和 Task 写入接口，未实测 API 创建后的通知。 [HubSpot Deal API](https://developers.hubspot.com/docs/api-reference/legacy/crm/objects/deals/guide) · [HubSpot Task API](https://developers.hubspot.com/docs/api-reference/legacy/crm/activities/tasks/guide) · [客户工单地址 ADR](https://github.com/raingxm/rtc-support-to-sales-inbox/blob/main/docs/adr/0012-customers-use-an-unguessable-ticket-address.md)

## 商机试点用同一组输入比较两条路径

1. 模拟客户说「我们准备把现有直播迁到 TRTC，想先做两周试点」，同时反馈技术问题。纯排障工单用于对照，两张工单都保留客户原话。
2. 支持人员从混合工单确认商机，指派解决方案工程师 A。A 能找到一条待跟进记录，看到是哪一句客户原话、哪张工单。纯排障工单没有该记录。客户入口没有因此新增消息。
3. A 记录「周五演示屏幕分享」，再记录实际结果「客户希望先验证 Android 弱网」。刷新后仍看到本人记录和来源，支持人员仍可在原工单排障。
4. 支持人员撤销商机，A 的当前待办随之结束。确认或撤销的操作者仍可核对。若选择自动 CRM 路径，再验证重试不产生第二条外部记录，并以试点账号确认通知真的送达。
