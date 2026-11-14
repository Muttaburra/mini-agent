# Week 1 Day 5：Step 3C → Step 4 → Step 5

本记录按用户提供的阶段规划整理，仅覆盖本次 API 故障处理的离线验收。

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| Step 3C | Mock API 异常测试 | 自动化验收通过 |
| Step 4 | Timeout 和 Retry 策略 | 实现完成，自动化验收通过 |
| Step 5 | 故障注入与最终验收 | 离线自动化验收通过 |

## Step 3C：应用如何处理异常

SDK 方法由 Mock 替换，真实请求封装处理超时、网络错误和限流。
验证异常日志、None 返回值、耗时、参数透传，以及 Agent 的 api_failed 状态。
原有单次尝试测试继续保留。

## Step 4：Timeout 和 Retry 各负责什么

`llm_client.LLM_TIMEOUT` 集中配置各网络阶段的等待上限，Agent 将其传给 OpenAI：

| 阶段 | 秒 | 含义 |
| --- | ---: | --- |
| connect | 5 | 建立连接的等待 |
| read | 30 | 等待读取数据的间隔 |
| write | 10 | 等待发送数据的间隔 |
| pool | 5 | 等待连接池可用连接 |

这些不是整个请求或整个 Agent 的总时限，不能简单推导出任务最多运行多少秒。

重试仍由 request_llm 统一负责：Agent 最多尝试 3 次，中间等待 1、2 秒；
增加尝试次数时，等待时间翻倍但单次最多 8 秒。SDK max_retries=0，避免嵌套重试。
超时、连接错误和 429 可重试；认证及其他 API 状态错误立即结束；编程错误向上传播。

## Step 5：更接近真实调用的故障注入

调用链：真实 Agent → 真实 request_llm → 真实 OpenAI SDK → httpx2.MockTransport。

测试不再直接构造 SDK 异常，而是注入底层超时/连接异常或返回 HTTP 429，
由真实 SDK 负责转换，随后验证应用日志和最终状态。
客户端使用测试凭证和保留域名 example.invalid，所有 HTTP 由内存传输处理。
工具执行和 sleep 仍被替换，不读取 .env、不改写 workspace、不真实等待。

新增 5 个测试方法，含 27 个 HTTP 注入场景：

- 连接、读取、写入、连接池超时，网络错误和 429：6 种故障。
- 每种覆盖首次恢复、首次耗尽次数、后续恢复、后续耗尽次数：24 个场景。
- 400、401、500 按当前策略立即结束：3 个场景。

验收点包括：超时配置传到 HTTP 请求；SDK 异常分类正确；实际传输次数有界；
等待次数正确；后续重试的请求内容不变；本地工具只执行一次；最终状态正确。

## 复现

项目根目录执行完整测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

只运行 HTTP 故障注入：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_http_fault_injection.py -v
```

分阶段结果：Step 3C 回归 13 个测试通过（0.040 秒）；Step 4 更新后 13 个测试通过
（0.041 秒）；HTTP 故障注入 5 个测试通过（0.366 秒）。耗时随机器运行状态变化。

最终完整回归：18 个测试方法全部通过（0.359 秒）；`git diff --check` 通过。
未执行真实 API 请求，未覆盖实验数据，未提交或推送 Git。

## 验收边界

MockTransport 不验证真实网络计时、服务器限流行为或真实模型质量。
本阶段未实现 Retry-After、随机抖动、配额耗尽分类、5xx 重试及整体任务截止时间。
不重复执行本地工具不等于服务端恰好处理一次请求，超时后重试仍可能再次生成响应。

思考：若服务端每隔 20 秒发送一小段数据，read=30 秒是否能保证整个请求在 30 秒结束？
