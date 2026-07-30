# FinGPT 接入说明

## 架构

Third-Hand 不直接在 FastAPI 容器内加载 FinGPT，而是调用独立的 OpenAI 兼容推理服务：

```
Android -> Third-Hand API -> FinGPT inference service
                         -> DeepSeek fallback
```

原因：FinGPT 模型通常需要 GPU 和较大的运行环境，独立部署更方便升级。

## 配置

```env
THIRD_HAND_AI_PROVIDER=auto
FINGPT_BASE_URL=http://fingpt:8000/v1
FINGPT_MODEL=fingpt
DEEPSEEK_API_KEY=
```

`auto` 会优先使用 FinGPT，失败后使用 DeepSeek。

## 输出原则

模型只负责金融信息理解、情绪分类和事件分析：

- 不预测股价
- 不输出买卖指令
- 保留原始来源核验
- 输出需要结合规则引擎复核

## 推理接口

服务需要兼容：

```
POST /chat/completions
```

响应格式：

```json
{"choices":[{"message":{"content":"{...}"}}]}
```
