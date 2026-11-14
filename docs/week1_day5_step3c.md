# Week 1 Day 5 — Step 3C

本阶段：使用 Mock 验证 API 超时、网络错误和限流。

## 架构

`agent_loop.py → llm_client.request_llm(client, **kwargs) → client.responses.create`

移除了 Agent 中遮蔽导入的重复 request_llm 定义；首次和后续请求都显式传入 client。
保留已有工具、状态机、日志、计时和失败即停止的行为。

请求封装负责将 SDK 异常转换为 `(None, duration_ms)`，Agent 负责将其转换为
`RunStatus.API_FAILED`。Mock 替换 SDK 调用边界，封装和 Agent 控制流执行真实代码。

## 测试与运行

在项目根目录执行（不需要 API Key）：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

- 请求层：超时、网络错误、429 限流分别验证日志分类、None 返回值、调用次数与耗时。
- 成功路径：原样返回响应，透传所有请求参数。
- 编程错误：TypeError 向上传播，避免被当成 API 故障隐藏。
- Agent 初次失败：api_failed、0 轮、1 次请求、工具不执行。
- Agent 后续失败：api_failed、1 轮、2 次请求、工具只执行一次，并验证响应 ID 和调用 ID。

共 5 个测试方法；3 个参数化方法各包含 3 个异常子场景，合计 11 个场景。
测试使用本地安装的 OpenAI SDK 异常类型和 httpx2 请求/响应对象；构造这些对象不发送请求。
Agent 测试替换了客户端构造、环境加载和工具执行，不读写 workspace 实验数据。

## 理解 Mock

`return_value` 模拟成功响应；`side_effect` 模拟异常或“先成功、再失败”的序列。
`patch("llm_client.time.perf_counter", ...)` 固定计时结果，避免依赖机器速度或真实等待。
`assertLogs` 同时检查日志级别与文本。

APITimeoutError 继承 APIConnectionError，捕获顺序必须从具体到一般。
Mock 测试验证的是应用处理 SDK 最终返回/抛出结果的行为，不验证真实网络、服务端
限流或 SDK 内部重试；一次 create 调用不代表真实环境只有一次 HTTP 请求。
本阶段没有添加重试策略，也没有运行真实 API 请求。

思考：如果将超时捕获移到网络错误捕获之后，哪条日志断言会失败？
如果需要重试，为什么应该先决定哪些异常可重试，再设计最大次数和退避时间？
