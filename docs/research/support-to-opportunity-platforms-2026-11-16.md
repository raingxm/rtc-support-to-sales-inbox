# 客服对话与销售对象：一手来源核对（2026-11-16）

研究日：2026-11-16。只采用当天打开过的厂商文档、产品页、价格页，或项目自己的 README / LICENSE。页面若自带日期，写在该条下面。搜索摘要里出现、但没有打开成功的行为，不写入对照。

核对的问题只有一件：一条客服对话，会不会从这同一条对话产生一个销售对象。只做帮助台、或只做 CRM 的产品，各写一句后跳过。

## 当前 demo 的边界

RTC Support-to-Sales Inbox 的用户是支持坐席。输入是一封客户信。模型做分诊：混合（支持问题加上商业意图）、仅支持、或需要澄清。商业证据必须是信里的原话。人确认之后，指定的解决方案工程师接手跟进。支持工单保持打开。系统不回复客户。没有商机管道、阶段或金额。

## 从客服对话产生销售对象

### Intercom Fin

- 是什么：一个客户代理，按角色做服务、销售和电商。帮助页作者 Beth-Ann Sher，日期 September 22, 2026。
- 用户：终端客户与 Fin 对话。销售角色把机会路由给销售团队。配置的人在 Fin AI Agent 里选择 Service、Sales 或 Ecommerce。
- 是否回复客户：回复。销售角色 “runs inbound conversations end to end”。电商角色在同一条对话里处理退货、退款和订单变更，问题处理完再把购物者带回浏览。
- 从对话产生的销售对象：销售角色按剧本询问 use case、budget、fit、timing，通过 Calendly 预约，把合格买家带进 trial 或 subscription，并 “syncs directly with your CRM—routing opportunities to your sales team with full context”。FAQ 写 Sales “qualifies and route leads to your sales team”。
- 人是否先确认：文档写的是端到端，没有写每条对话要人确认后对象才存在。
- 是否保留客户原话：该页没有写必须保留客户原话作为证据。
- 价格：价格页未打开。未核对价格。
- 来源：<https://www.intercom.com/help/en/articles/12508017-fin-as-a-customer-agent-for-service-sales-and-more>

服务与销售的受众规则重叠时，Fin “prioritize the sales role and seamlessly switch to the service role if it detects a support question that it can't answer”。同一条对话可以在销售和支持之间切换。旧文 “Generating leads with Intercom” 返回 401，下面不使用那一页。

### Zendesk Support 与 Sell

- 是什么：Support 工单里的 Sell 应用。前提是 “You must have Sell and Support”。
- 用户：支持坐席。坐席在工单上创建 lead，或给已有 lead / contact 的负责人发通知。
- 是否回复客户：创建 lead 这一步写的是给 Support 工单加一条评论，评论说明 lead 已交给 Sell。这一步没有写给客户发回复。Support 本身是坐席用来提供服务的产品。
- 销售对象：Sell 里的 lead。没有匹配的 lead 或 contact 时，才出现 Create lead。请求人的姓名、邮箱、电话、X、Facebook 和组织名写入联系信息。可选填一条 note。lead 的 status、owner、source 按集成设置。坐席可能要选择一个 distribution，或指定一名 sales rep。Sell 活动流里留下指向该工单的链接。
- 人是否先确认：要。坐席点击 Create lead，再点击 Create。
- 是否保留客户原话：可选的是坐席自己写的 note，文档没有要求摘录客户原话。
- 价格：2026-11-16 打开的 <https://www.zendesk.com/pricing/> 没有单独的 Sell 价格。该页服务方案年付 / 月付（per agent / month）：Support Team $19 / $25；Suite Team $55 / $69；Suite Professional $115 / $149。Suite Enterprise + Copilot 为 Talk to Sales。Sell 价格未核对。
- 停用：<https://support.zendesk.com/hc/en-us/articles/9591462550042-Announcing-the-retiring-of-Zendesk-Sell> 写 Announced on September 9, 2025，Retired on August 31, 2027。到期前客户仍可使用 Sell。Zendesk 写明此后不再提供 sales CRM，并指向 Pipedrive 的 Zendesk 集成。该停用页没有描述 Pipedrive 如何从工单创建 lead，这里不转述那一步。
- 来源：<https://support.zendesk.com/hc/en-us/articles/4408831980314-Working-with-the-Zendesk-Sell-app-in-Support>

### HubSpot Service Hub 与 Deal

- 是什么：Help Desk 管 ticket 和对话；Deal 是可与 ticket 关联的 CRM 对象。
- 用户：持有 Service 或 Sales Access、并 respond to tickets 的人。Help Desk 页写 Service Hub Professional、Enterprise，高级功能需要 Service Seat。页上日期 Last updated: September 7, 2026。
- 是否回复客户：会。权限句是 “view, edit, and respond to tickets”。同一页有回复编辑器、Start new conversation、End chat and keep the ticket open。
- 销售对象：Deal。Help Desk 右侧栏展示并更新关联的 contacts、companies、deals。关联记录页（Last updated: September 16, 2026）写：处理客户投诉、而对方同时又在购买时，可以把 ticket 关联到 deal。从记录侧栏可以 Create new，新建记录并关联。
- 人是否先确认：已打开的页面写的是人在侧栏创建或关联。没有写模型从工单正文自动生成 deal。
- 是否保留客户原话：这两页没有写把客户原话锁成证据。Breeze Assistant 可根据对话生成工单名称和摘要，那是生成文本。
- 价格：价格页未打开。未核对价格。Help Desk 页写明 Service Hub Professional、Enterprise。
- 来源：<https://knowledge.hubspot.com/help-desk/manage-tickets-in-help-desk> ，<https://knowledge.hubspot.com/records/associate-records>

### Freshdesk 与 Freshsales

- 是什么：Freshdesk 工单上的 Freshsales 应用。支持坐席查看 lead、contact、deal、account，并从工单创建销售记录。文章 Modified on: Fri, 6 Jun, 2025。同一 URL 里有两段功能说明，下面都来自这一页。
- 用户：Freshdesk 坐席创建或关联；Freshsales 用户在 Contacts、Leads、Deals、Accounts 上看到链接的工单，并可 View in Freshdesk。
- 是否回复客户：应用说明的目的包括让坐席 “tailor their responses”。创建记录本身没有写自动给客户发信。
- 销售对象：点击 “create lead/contact”，把工单上的销售询问转成 Freshsales 的 lead 或 contact。自动带入的是 First name、Last name、Email、电话、Company、社交链接、Address、Job Title、Time Zone。另一段写：打开 Deal Fields 且勾选 “Agents can create/link or unlink deals from the ticket” 之后，坐席可以从工单创建、关联或解除 deal。一个 deal 可以连多张工单；每张工单只能连一个 deal。管理员可以关掉创建和关联，只留查看。
- 人是否先确认：要。坐席点击创建或关联。管理员可以禁止。
- 是否保留客户原话：写入的是请求人资料字段。该页没有写保存客户原话。
- 价格：价格页未打开。未核对价格。该页写联系人信息增强，以及 Deal 与 Ticket 的链接，在列出的 Freshdesk 与 Freshsales plans 上均为 All Plans。
- 来源：<https://support.freshdesk.com/support/solutions/articles/219923-how-to-integrate-freshsales-with-freshdesk->

### Ada 的 Salesforce Action block

- 是什么：Ada 的 AI Agent 在 Handoff 对话里调用 Salesforce。同一块也可以创建、更新、查找 Case。
- 用户：终端客户在对话里说话。搭建对话的人把 Salesforce Action block 拖进 dialog。Lead 进入 Salesforce，供销售侧使用。
- 是否回复客户：这是客户面对的 AI Agent。交接文档写的是对话过程中的动作。
- 销售对象：Create a Lead，或 Update a Lead。文档用的句子是 “Create or update leads with information collected during chat”。必填 Salesforce 字段要映射 Ada 变量。
- 人是否先确认：文档写的是流程走到这个 block 就执行。没有写每条对话要人点确认后 lead 才出现。
- 是否保留客户原话：映射的是变量和字段。没有写必须保存客户原话。
- 价格：该页写功能可能不在订阅包内，并指向 Ada 的 Pricing page。价格页未打开。未核对价格。
- 来源：<https://docs.ada.cx/docs/handoffs/salesforce/salesforce-chat/salesforce-action-block.mdx>

### Gainsight Staircase AI Expansion Analyst

- 是什么：在账户页上，从近期客户沟通里标出扩张信号。用户是 Customer Success Manager 和 Account Manager。
- 是否回复客户：不回复。它阅读已有的 emails、meetings、support tickets。
- 销售对象：产品内是一条 AI opportunity：摘要、readiness score、ARR potential（如果沟通里谈到过金额）、证据面板。流程概述接着写，人决定是否推进之后，“Create or update the opportunity record in your connected CRM system”。同一篇文章随后写：Expansion Analyst does not connect to Salesforce，不从 Salesforce 拉 opportunity，不同步 CRM 阶段，不自动更新 Salesforce。因此已核实的产品内对象是 AI 机会卡；Salesforce Opportunity 不会由它自动写下。
- 人是否先确认：要。人 review 证据，再决定 pursue 或 dismiss。
- 是否保留客户原话：写了。每条机会包含 “Direct quotes that highlight expansion signals”，证据面板可看原话、参与者和日期。参考卡写明 direct quotes（谁说的）、说话人的 name、role、company。
- 范围：账户在过去 90 天有沟通才进入分析。完整重跑大约每三周一次，且至少有一条新互动。续约后暂停 90 天。输入是一段时期内的多条沟通，不是单独一封仍打开的支持信。
- 价格：价格页未打开。未核对价格。
- 来源：<https://support.gainsight.com/Staircase_AI/Staircase_AI_Features/Expansion_Analyst> 。该页没有显示发布日期。

### DevRev

- 是什么：同一产品里有 ticket、conversation 和 opportunity。Opportunity “represents a potential source of revenue”，有可配置的 states 和 stages。
- 用户：创建机会的人填写 owner。文档写 owner 把机会分给 sales representatives 或 customer-facing team members。
- 是否回复客户：本次打开的 Opportunity 页没有写回复行为。
- 销售对象：Opportunity。可以链接到 account、tickets 和 conversations。创建入口是 Explore > Opportunities：title、description、owner、account。库存字段包括 Stage、Total value、Forecast category。阶段分组里有 Qualification、Stalled、Validation、Negotiation、Contract、Closed Won、Closed Lost。
- 人是否先确认：创建是人点击 + Opportunity。文档写的是把机会链接到工单或对话，没有写从工单正文自动生成机会。
- 是否保留客户原话：该页没有写。
- 价格：价格页未打开。未核对价格。
- 来源：<https://support.devrev.ai/en-US/devrev/article/VSU6Qz6K-opportunity> 。页上没有文章日期。

### Plain

- 是什么：支持工单上的分诊工作流 “Route expansion inquiries to Sales”。页脚 © 2026 Not Just Tickets Ltd.
- 用户：工作流把工单送给 Sales queue。页面没有写具名个人。
- 是否回复客户：这一页没有写回复客户。
- 销售对象：没有 lead、deal 或 opportunity。它 “labels those tickets for Sales”。触发是客户询问 more seats、a higher plan 或 a bigger usage limit。它检查开场消息和之后的每一条客户回复，“a buying signal that surfaces halfway through a support conversation still gets caught”。“Those requests reach your Sales queue instead of sitting in support triage.”
- 人是否先确认：页面写的是工作流直接打标并送进销售队列。
- 是否保留客户原话：没有写摘录原话。
- 价格：价格页未打开。未核对价格。
- 来源：<https://www.plain.com/workflows-library/route-expansion-inquiries-to-sales>

## 同一产品里两边都有，但不是从客服对话生成销售对象

**Gorgias。** AI Agent 页（页上 “Updated 2 months ago”，没有绝对日期）写同一个 AI Agent 有两个角色，区别在于它正在回复的是哪一种对话：Support agent 处理购后的退货、订单跟踪、取消和缺件；Shopping Assistant 在购前的 email、chat、SMS 和社交渠道里帮人找到商品并完成购买。指标页写：订单记到 Shopping Assistant，条件是客户在 Shopping Assistant 最后一条消息之后 3 天内下单；若对话交给人，attribution is voided。收入统计产品页用了 “tickets converted to sales”，已打开的角色说明和指标定义把销售归因放在购前购物角色上。价格页未打开。未核对价格。来源：<https://docs.gorgias.com/en-US/ai-agent-explained-497772> ，<https://docs.gorgias.com/en-US/how-metrics-are-calculated-ai-and-automation-5666070> ，<https://www.gorgias.com/product/revenue-statistics>

**Decagon。** 技术行业页把三件事并列：Inbound support 解决工单；Lead qualification 在定价页和产品页接触潜在客户、qualify new leads，并 “route opportunities to sales”；另外是 onboarding。CRM 一行是与 Salesforce、HubSpot 同步，使 lead 和客户上下文放在一处。该页没有写一张支持工单生成一条 opportunity。价格页未打开。未核对价格。来源：<https://decagon.ai/industry/technology>

**Forethought。** Qualify 页写它是 “the AI agent platform for CX that also accelerates pipeline”，并用同一套 CX agent “qualify leads, capture intent, and route prospects to the right sales path”。捕获的是 account data、ARR 和 intent，再路由到 self-serve、BDR 或 AE。该页把 qualify 写成一个 customer moment，没有写支持工单正文变成 opportunity，也没有写保留客户原话或人先确认。价格页未打开。未核对价格。来源：<https://forethought.ai/by-customer-moment/qualify>

**erxes。** `main` README 把 Frontline 和 Sales 分成两个插件。Frontline 是 “Omnichannel conversations, tickets, tasks”。Sales 的句子是用 landing page、forms、pop-up 或 embed 把访客变成 qualified leads。README 没有写从收件箱对话生成 deal。`main` 上的 `LICENSE` 路径打开为 404。`master` 的 LICENSE.md 写：名称以 “-ee” 结尾、位于 `ee/` 的插件用 `ee/LICENSE`；其余内容为 AGPLv3；并写 “erxes is not permitted to be hosted as a SaaS version to compete with erxes Inc.” 来源：<https://github.com/erxes/erxes/blob/main/README.md> ，<https://github.com/erxes/erxes/blob/master/LICENSE.md>

**Chaskiq。** README 标题是 Messaging Platform for Marketing, Support & Sales，功能列表有 “CRM integration - Pipedrive supported”。同一 README 没有写从一条客服对话创建 deal。许可证段落写商业许可证用于避开 “AGPL-3.0-or-later + commons clause”。来源：<https://github.com/chaskiq/chaskiq/blob/main/README.md>

**Pylon。** Opportunities 页写机会属于一个 account，在 Customers 下 Add Opportunity，并可映射到 CRM 记录。自定义字段可以跟踪 stages、amounts、dates、owners。该页写机会在部分方案上提供，具体要联系客户团队。它没有写从支持对话生成机会。价格页未打开。未核对价格。来源：<https://docs.usepylon.com/pylon-docs/account-intelligence/opportunities>

**Thena。** Work unit 在底层用 ticket 系统实现，界面上可以叫做 tickets、cases、opportunities 或 bugs。文档写 “each team can have only one type of work unit”。销售别名可以带 deal value、probability、expected close date 和阶段。这是同一个工作对象的别名，不是从一条支持对话再创建第二个销售对象。来源：<https://docs.thena.ai/platform/core-concepts/work-units>

**Sierra。** 首页写 “Go beyond customer service to drive revenue growth”，以及按 guardrails “maximize satisfaction and revenue”。首页没有写从对话创建 lead、deal 或 opportunity。价格页未打开。未核对价格。来源：<https://sierra.ai/>

## 只做一侧

- **Gladly。** 词汇表把工作单位写成 Conversation：客户不会被分配 ticket 或 case number，一个客户同时只有一条打开的 Conversation。已打开的该页没有从对话创建 lead、deal 或 opportunity。来源：<https://help.gladly.com/docs/glossary-and-key-concepts>
- **Kustomer。** 已打开的对话帮助写的是回复、状态和把对话彼此关联。没有写从对话创建 lead 或 opportunity。来源：<https://help.kustomer.com/en_us/categories/work-with-conversations-HJCoEHDqle>
- **Qualified。** 首页产品是 AI SDR Piper：在网站和邮件里接触入站买家、捕获 leads、把合格买家变成 pipeline。首页没有客服工单。来源：<https://www.qualified.com/>
- **Drift。** <https://www.drift.com/> 打开后没有产品正文。Salesloft 页写 “We've transitioned from Drift to 1mind”，产品是网站访客聊天进入销售 pipeline，并触发 seller 的 Rhythm 动作。该页没有客服工单，也没有从支持对话创建商机。来源：<https://www.salesloft.com/platform/drift>
- **Chatwoot。** README 自称为开源客户支持平台。Captain 自动回复常见问题。功能列表没有 deal、lead 或 opportunity。MIT License，版权行 2017–2026 Chatwoot Inc。来源：<https://github.com/chatwoot/chatwoot/blob/develop/README.md>
- **Papercups。** README 写它是开源实时客服，处于 maintenance mode。功能是聊天、邮件、短信和会话分配。MIT。来源：<https://github.com/papercups-io/papercups/blob/master/README.md>
- **Zammad。** README 写它是开源 helpdesk，渠道包括 email、chat、telephone 和 social。GNU AGPLv3。没有销售对象。来源：<https://github.com/zammad/zammad/blob/develop/README.md>
- **FreeScout。** README 写它是 help desk 和 shared inbox。LICENSE 文件为 GNU Affero General Public License Version 3。README 没有销售对象。来源：<https://github.com/freescout-helpdesk/freescout/blob/master/README.md> ，<https://github.com/freescout-helpdesk/freescout/blob/master/LICENSE>
- **Twenty。** README 自称为开源 CRM。示例对象是 deal，字段含 amount 和 close date。没有客服对话。来源：<https://github.com/twentyhq/twenty/blob/main/README.md>
- **Krayin。** README 是 Laravel CRM，MIT。WhatsApp 扩展的句子是用 WhatsApp 号码生成 leads。没有从客服工单生成商机。来源：<https://github.com/krayin/laravel-crm/blob/master/README.md>
- **SuiteCRM。** Cases 文档写 Case 记录客户求助，关联是 Contacts、Account、Bugs、Activities、History、Documents。关联列表里没有 Opportunity。Opportunities 是另一份销售文档里的管道对象。因此这套 CRM 同时有支持案例和销售机会，已打开的 Cases 页没有从 Case 生成 Opportunity。Cases 页注明文档本身使用 GNU Free Documentation License 1.3 or later。来源：<https://docs.suitecrm.com/8.x/user/customer-service/cases/>

## 和当前 demo 边界的对照

没有任何一份已打开的一手页面同时落在全部边界内：用户是支持坐席、输入是一封信、证据是客户原话、人确认后交给具名负责人、支持工单保持打开、系统不回复客户、没有管道、阶段和金额。

| 产品 | 相对这条边界 |
| --- | --- |
| Zendesk Support → Sell lead | 支持坐席点击后 lead 才出现，工单留下评论。可选指定 sales rep 或 distribution。创建步骤没有写给客户发信。证据是坐席可选 note，不是客户原话。对象是 lead，带集成里配置的 status。Sell 将于 2027-08-31 停用。 |
| Freshdesk → Freshsales lead / deal | 支持坐席点击后才有 lead、contact 或 deal。工单仍在，并与销售记录互链。写入的是联系人字段。应用目的包括帮助坐席回复客户。deal 是销售记录，一张工单只能连一个 deal。 |
| HubSpot ticket 与 deal | 人在工单侧栏关联或新建 deal。坐席会回复客户。已打开的页面没有原话锁，也没有写自动从正文生成 deal。 |
| Intercom Fin | 在边界的客户一侧。同一条对话可在销售角色和支持角色之间切换。Fin 自己回复，并同步 CRM、路由 opportunities、预约会议。没有人先确认，也没有原话锁。 |
| Ada Salesforce Create a Lead | 在边界的客户一侧。对话流程可以创建 Salesforce lead。客户面对 AI Agent。确认发生在流程设计，文档没有写每封信由人确认。 |
| Gorgias Shopping Assistant | 在边界的客户一侧，而且销售发生在购前对话。交给人之后，订单归因作废。支持角色是另一类对话。 |
| Gainsight Expansion Analyst | 证据和人的决定最接近：direct quotes，人选择 pursue 或 dismiss，并且明确不自动写 Salesforce。用户是 CSM / 客户经理。输入是账户 90 天内的邮件、会议和工单。它不经营这一张仍打开的支持工单，也不指定解决方案工程师。 |
| Plain | 购买信号可以出现在支持对话中途。工作流把这张工单打标并送进 Sales queue，工单离开支持分诊。没有第二个销售对象，没有人确认，没有原话锁。 |
| DevRev | 人另建一条带阶段、预测类别和 Total value 的 opportunity，再链接到 ticket 或 conversation。销售管道在产品内。 |

## 未覆盖

- **Salesforce Service Cloud 的 Case to Opportunity、以及 Einstein。** 没有打开到一篇写 “从 Case 创建 Opportunity” 的帮助页。搜索命中并展示过正文的是 Lead 转换：合格 lead 转成 contact，并可同时创建 opportunity（<https://help.salesforce.com/s/articleView?id=sales.leads_convert.htm&language=en_US&type=5>）。Messaging 页 “associate the session with a case, lead, or opportunity” 只出现在搜索结果里，WebFetch 超时，不写入对照。Agentforce 销售代理页描述的是网站访客成为 lead，那是销售对话。
- **Vitally。** 没有打开到「工单正文变成 expansion opportunity」的文档。搜索摘要中的 Inspiration 示例触发条件是购买额度，不是工单原文，故整段省略。
- **Gladly 的 HubSpot 应用是否写入 CRM。** 搜索摘录写 Gladly 只读、never writes。该页没有单独打开，不把这句话当作已核实行为。
- **Kustomer 的订单收入归因。** 只在博客出现，帮助中心已打开的页面没有这条行为，省略。
- **价格页未打开，一律未核对价格：** Intercom、HubSpot、Freshworks、Plain、DevRev、Ada、Gainsight、Decagon、Forethought、Sierra、Gorgias，以及 Zendesk Sell 的单独价格。Zendesk 服务方案价格来自已打开的 <https://www.zendesk.com/pricing/> 。
- **erxes 文档站**没有打开到「对话生成 deal」的页面。结论只依据 `main` README 和 `master` LICENSE.md。
