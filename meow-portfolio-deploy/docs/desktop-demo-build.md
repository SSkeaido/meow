# 桌面演示版打包说明

## 1. 当前桌面版形态

本项目已经接入 Electron 桌面壳，可以作为本地桌面演示版运行。

桌面版启动后会自动完成：

```text
打开桌面窗口
→ 自动启动本地 Node 后端
→ 前端通过本地 API 调用 RAG/LLM 审查接口
→ 展示四页式风险审查工作台
```

## 2. 本地启动

首次使用先安装依赖：

```bash
npm install
```

启动桌面演示版：

```bash
npm run desktop
```

或：

```bash
npm start
```

## 3. 打包目录版

目录版适合本机演示和调试：

```bash
npm run pack
```

输出位置：

```text
dist/win-unpacked/装修签约前风险审查助手.exe
```

运行时需要保留整个 `win-unpacked` 文件夹，不要只单独复制 exe。

## 4. 打包便携版 exe

便携版适合发给别人试用：

```bash
npm run dist
```

输出位置：

```text
dist/装修签约前风险审查助手-0.1.0.exe
```

该 exe 会在启动时解压到系统临时目录并运行，首次打开可能稍慢。

## 5. LLM 配置

默认不配置 API Key 时，桌面版会使用：

```text
LLM_PROVIDER=mock
```

也就是本地规则/RAG 兜底演示，不会调用外部模型。

如果要接入硅基流动或其他 OpenAI-compatible API，可在项目根目录创建 `.env.local`：

```text
AGENT_HOST=127.0.0.1
AGENT_PORT=8792

LLM_PROVIDER=siliconflow
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
LLM_FALLBACK_MODELS=deepseek-ai/DeepSeek-V3,deepseek-ai/DeepSeek-R1-Distill-Qwen-7B
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_API_KEY=你的 API Key
```

注意：`.env.local` 已加入 `.gitignore`，不要把真实 API Key 提交到 git。

## 6. 当前验证结果

已验证：

- `npm run desktop` 可以启动桌面窗口。
- 桌面版会自动启动本地后端。
- `http://127.0.0.1:8792/api/health` 返回正常。
- `npm run pack` 可生成目录版。
- `npm run dist` 可生成便携版 exe。

## 7. 当前边界

当前是作品集/演示版，不是正式商业软件。

仍需补充：

- 真实安装器和图标签名。
- API Key 配置界面。
- 用户隐私协议确认。
- 文档上传解析。
- 更新机制。
- 错误日志可视化。

