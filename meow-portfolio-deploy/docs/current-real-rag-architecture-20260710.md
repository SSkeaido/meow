# 当前项目架构图：业主装修签约前 RAG 风险审查助手

生成时间：2026-07-10

当前项目已经从早期“前端规则 + 本地知识库展示”推进为：

> **前端输入 → 后端 RAG 检索 → LLM 风险审查 Agent → 结构化风险报告 → 前端展示**

这份文档只描述当前代码中的真实实现，不描述理想设想。

---

## 1. 当前整体架构图

```mermaid
flowchart TD
    U["业主 / 使用者<br/>输入报价单、合同、销售沟通记录"] --> FE["前端工作台<br/>index.html / app.js / styles.css"]

    subgraph FE_LAYER["前端展示层"]
        P1["页面 1：资料输入"]
        P2["页面 2：AI 审查过程"]
        P3["页面 3：风险提示总览"]
        P4["页面 4：结构化报告"]
    end

    FE --> FE_LAYER
    FE --> API["后端 Agent API<br/>http://127.0.0.1:8792"]

    subgraph API_LAYER["后端 API 层"]
        H1["GET /api/health"]
        H2["POST /api/rag/retrieve<br/>只执行 RAG 检索"]
        H3["POST /api/owner-risk/review<br/>完整风险审查链路"]
        H4["POST /api/sales/run-workflow<br/>旧销售端工作流接口，保留"]
    end

    API --> API_LAYER

    H3 --> ROUTER["知识路由器<br/>server/rag/knowledgeRouter.js"]
    ROUTER --> RETRIEVER["RAG 检索器<br/>server/rag/retriever.js<br/>关键词 + embedding 混合检索"]
    RETRIEVER --> REVIEW_AGENT["业主风险审查 Agent<br/>server/agents/ownerRiskReviewAgent.js"]

    subgraph KB_LAYER["知识库层"]
        MASTER["主知识库<br/>knowledge/owner-risk-rag-master.json<br/>165 条知识卡"]
        REGISTRY["合同模板注册表<br/>knowledge/contract-template-registry.json"]
        CONTRACT["合同模板知识卡<br/>contract-template-cards.json"]
        SUPPLEMENT["补充知识库<br/>验收/材料标准 + 案例库"]
        VECTOR["向量索引<br/>knowledge/index/owner-risk-vector-index.json<br/>165 条 embedding"]
    end

    ROUTER --> REGISTRY
    RETRIEVER --> MASTER
    RETRIEVER --> VECTOR
    MASTER --> CONTRACT
    MASTER --> SUPPLEMENT

    REVIEW_AGENT --> LLM_CLIENT["LLM Client<br/>server/llm/llmClient.js"]

    subgraph LLM_LAYER["LLM 层"]
        QWEN["主模型<br/>Qwen/Qwen2.5-7B-Instruct"]
        FALLBACK1["备用模型<br/>DeepSeek-R1-Distill-Qwen-7B"]
        FALLBACK2["备用模型<br/>DeepSeek-V3"]
        LOCAL_FALLBACK["RAG 确定性兜底<br/>模型失败时仍返回报告"]
    end

    LLM_CLIENT --> QWEN
    QWEN -->|失败 / 限流 / 超时| FALLBACK1
    FALLBACK1 -->|失败 / 限流 / 超时| FALLBACK2
    FALLBACK2 -->|失败 / 非 JSON| LOCAL_FALLBACK

    QWEN --> RESULT["结构化审查结果 JSON"]
    FALLBACK1 --> RESULT
    FALLBACK2 --> RESULT
    LOCAL_FALLBACK --> RESULT

    RESULT --> FE
    FE_LAYER --> OUT["最终输出<br/>风险摘要 / 风险卡片 / 追问清单 / 结构化表格 / CSV"]
```

---

## 2. 当前 RAG 审查主流程图

```mermaid
sequenceDiagram
    participant User as 业主/用户
    participant FE as 前端工作台
    participant API as 后端 /api/owner-risk/review
    participant Router as 知识路由器
    participant Retriever as RAG 检索器
    participant KB as 主知识库
    participant LLM as LLM 审查 Agent
    participant UI as 四页展示界面

    User->>FE: 输入城市、面积、装修模式、报价单、合同、沟通记录
    FE->>API: POST /api/owner-risk/review
    API->>Router: 识别城市与审查阶段
    Router->>Router: 优先匹配地方合同模板
    Router->>Router: 无地方模板则回退全国模板
    Router->>Retriever: 传入地区、阶段、模板策略、用户材料
    Retriever->>KB: 检索 owner-risk-rag-master.json
    KB-->>Retriever: 返回候选知识卡
    Retriever->>Retriever: 阶段过滤 + 模板过滤 + 触发词匹配 + embedding 相似度 + 词项评分 + 可信层级加权
    Retriever-->>API: 返回 Top-K 审查依据
    API->>LLM: 用户材料 + Top-K 审查依据
    LLM-->>API: 风险等级、风险卡片、追问清单、人工复核事项
    API-->>FE: 返回结构化 JSON
    FE->>UI: 渲染 AI 审查过程、风险总览和结构化报告
```

---

## 3. RAG 与 LLM 的真实关系

当前项目中，RAG 和 LLM 不是两条并列线，而是串联关系：

```mermaid
flowchart LR
    INPUT["用户原始材料"] --> ROUTE["知识路由<br/>城市 / 阶段 / 模板"]
    ROUTE --> RETRIEVE["RAG 检索<br/>关键词 + embedding<br/>召回可信依据"]
    RETRIEVE --> CONTEXT["构造上下文<br/>用户材料 + 命中依据"]
    CONTEXT --> LLM["LLM 审查 Agent"]
    LLM --> REPORT["结构化风险报告"]
```

也就是说：

```text
RAG 不是单独输出结论。
RAG 负责把合同模板、消费提示、案例经验、验收标准等依据找出来。
LLM 再基于这些依据生成风险解释、追问清单和人工复核事项。
```

---

## 4. 知识库路由逻辑

```mermaid
flowchart TD
    START["用户填写城市与审查阶段"] --> CITY["识别省份/城市"]
    CITY --> LOCAL{"是否有地方/区域合同模板？"}

    LOCAL -->|有| LOCAL_TEMPLATE["优先使用地方/区域模板<br/>例如：京津冀、黑龙江"]
    LOCAL -->|无| NATIONAL["回退全国模板<br/>GF—2000—0207"]

    LOCAL_TEMPLATE --> ADD_NATIONAL["同时补充全国模板"]
    ADD_NATIONAL --> FILTER["按审查阶段过滤知识卡"]
    NATIONAL --> FILTER

    FILTER --> STAGE1["签约前：报价、合同附件、付款节点、增项风险"]
    FILTER --> STAGE2["施工中：变更、验收、责任边界、返工风险"]
    FILTER --> STAGE3["交付后：结算、保修、空气质量、售后责任"]
```

当前示例：

| 用户所在地 | 当前策略 |
| --- | --- |
| 北京 / 天津 / 河北 | 京津冀示范文本 + 全国模板 |
| 黑龙江 / 哈尔滨等 | 黑龙江地方模板 + 全国模板 |
| 杭州 / 广州等暂无地方模板城市 | 全国模板 |

---

## 5. 知识库分层

当前前端和后端共同使用主库：

`knowledge/owner-risk-rag-master.json`

总计 165 条知识卡。

```mermaid
flowchart TD
    MASTER["owner-risk-rag-master.json<br/>165 条"] --> A1["A 合同硬知识<br/>12 条"]
    MASTER --> A2["A 合同模板知识<br/>8 条"]
    MASTER --> A3["A 验收/材料标准<br/>20 条"]
    MASTER --> B["B 消费提示<br/>15 条"]
    MASTER --> C["C 案例库<br/>100 条"]
    MASTER --> D["D 经验/基础规则<br/>10 条"]
```

每条知识卡现在都带有：

| 字段 | 作用 |
| --- | --- |
| `origin_file` | 追溯来自哪个源文件 |
| `source_tier` | A/B/C/D 可信层级 |
| `source_bucket` | 合同硬知识、合同模板知识、消费提示、案例库等具体分类 |
| `applicable_stages` | 适用签约前、施工中还是交付复核 |
| `template_id` | 对应哪个合同模板 |

当前向量索引：

| 文件 | 说明 |
| --- | --- |
| `knowledge/index/owner-risk-vector-index.json` | 165 条知识卡的 embedding 向量索引 |
| `server/llm/embeddingClient.js` | embedding 生成客户端 |
| `scripts/build-vector-index.js` | 向量索引构建脚本 |

---

## 6. 模型调用与降级链路

当前后端模型配置：

```text
主模型：Qwen/Qwen2.5-7B-Instruct
备用 1：deepseek-ai/DeepSeek-R1-Distill-Qwen-7B
备用 2：deepseek-ai/DeepSeek-V3
最终兜底：RAG 确定性审查
```

```mermaid
flowchart TD
    REQ["LLM 审查请求"] --> M1["Qwen/Qwen2.5-7B-Instruct"]
    M1 -->|成功且 JSON 可解析| OK["返回 LLM 审查结果"]
    M1 -->|429 / 超时 / fetch failed| M2["DeepSeek-R1-Distill-Qwen-7B"]
    M2 -->|成功且 JSON 可解析| OK
    M2 -->|失败| M3["DeepSeek-V3"]
    M3 -->|成功且 JSON 可解析| OK
    M3 -->|失败或非 JSON| FALLBACK["RAG 确定性兜底结果"]
```

这意味着：

- 模型拥堵时不会导致系统崩溃
- 输出不是严格 JSON 时不会导致页面报错
- 最坏情况下仍然可以基于 RAG 命中依据生成风险报告

---

## 7. 当前代码模块对应关系

| 层级 | 文件 | 作用 |
| --- | --- | --- |
| 前端页面 | `index.html` | 四页工作台结构 |
| 前端交互 | `app.js` | 表单提交、接口调用、结果渲染、CSV 导出 |
| 前端样式 | `styles.css` | 风险审查工具 UI 样式 |
| API 服务 | `server/agent-server.js` | 暴露 health、RAG 检索、业主风险审查等接口 |
| 知识路由 | `server/rag/knowledgeRouter.js` | 城市识别、合同模板选择、阶段过滤 |
| RAG 检索 | `server/rag/retriever.js` | Top-K 依据召回、关键词 + embedding 混合打分、证据卡生成 |
| 风险审查 Agent | `server/agents/ownerRiskReviewAgent.js` | 将用户材料和 RAG 依据交给 LLM，生成结构化审查结果 |
| LLM 客户端 | `server/llm/llmClient.js` | 调用硅基流动/OpenAI-compatible 模型，支持降级 |
| Embedding 客户端 | `server/llm/embeddingClient.js` | 生成知识卡和查询文本向量 |
| 主知识库 | `knowledge/owner-risk-rag-master.json` | 当前 RAG 主库 |
| 向量索引 | `knowledge/index/owner-risk-vector-index.json` | 当前 embedding 向量索引 |
| 模板注册表 | `knowledge/contract-template-registry.json` | 地方/全国合同模板路由依据 |

---

## 8. 当前状态判断

当前项目可以定义为：

> **面向业主装修签约前风险审查的 RAG + LLM 原型。**

它已经具备真实 RAG 架构的关键要素：

- 有结构化知识库
- 有地区和阶段路由
- 有 Top-K 审查依据召回
- 有 embedding 向量索引和混合检索
- 有 LLM 审查 Agent
- 有模型降级和确定性兜底
- 有结构化结果展示

当前仍未完成的产品化能力：

- 当前 embedding 为本地 deterministic embedding；如需真实语义向量，可切换到硅基流动或本地 embedding 模型
- 尚未接入专业向量数据库
- 尚未对 PDF / Word / 图片附件做自动解析
- 尚未实现人工复核工单流转

---

## 9. 一句话版架构说明

> 用户提交装修签约材料后，系统先按所在地和审查阶段路由到对应合同知识库，再用关键词 + embedding 混合 RAG 检索命中审查依据，随后把“用户材料 + 命中依据”交给 LLM 风险审查 Agent，最终生成可解释、可追问、可导出的风险审查报告。
