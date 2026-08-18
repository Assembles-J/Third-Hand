# Third-Hand（第三只手）

## 权威设计与运行边界

`docs/ThirdHand_Architecture_v3_consolidated.md` 与
`docs/ThirdHand_v3_Roadmap_and_Ledger.md` 是 v3 的唯一权威设计与交付台账；
README、界面文案、代码注释或部署变量与它们冲突时，以这两份文档为准并须同步修正。

Third-Hand 不连接券商、不保存券商凭据、不提交真实订单，也不承诺收益。项目可选的
paper trading 仅写入本地 CNY 模拟账本；启用自动纸面交易后，调度器可以自动创建模拟
成交。因此“不会自动下单”仅指不会提交真实券商订单，不能被理解为“不会写入纸面账本”。
`DECISION_SHADOW_MODE` 是研究/决策影子输出开关，不是纸面交易安全开关。

纸面执行必须遵守市场、交易时段、行情新鲜度、仓位 lot 和可卖数量约束；A 股当日买入
数量 T+1 锁定，不得被自动卖出。当前已知执行缺口、生产验证记录和修复验收标准都维护在
上述两份权威文档中。

面向 A 股新手的成长信息助手：帮助理解信息与持仓风险，**不提供买卖指令或收益承诺**。

## MVP 已覆盖

- 持仓：手工新增 / CSV 导入接口；券商或同花顺数据仅通过用户授权的导出文件接入。
- 新闻：新闻对象、股票/行业/概念实体关联、影响链路和来源跳转。
- 词条：把「回购、减持、PE」等术语解释为新手可读的卡片。
- 关注流：按持仓和自选股排序，给出“需要核实什么”的中性提示。
- 建议：当前仅为风险提示与待核查清单，结论必须附证据、时效和不确定性。

## 架构

```text
Android (Kotlin / Compose) ── HTTPS ── FastAPI
                                      ├── PostgreSQL（用户、持仓、订阅）
                                      ├── Redis + Celery（采集、去重、推送）
                                      ├── 新闻/RSS/授权数据源
                                      └── 规则 + LLM（实体、词条、关联、摘要）
```

客户端只保存登录令牌；持仓、导入文件和模型密钥都应在服务端加密处理。

## 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

浏览 `http://127.0.0.1:8000/docs`；Android 模拟器可将 API 地址设为 `http://10.0.2.2:8000/`。

## Android APK

用 Android Studio 打开 `android/`，选择 debug 变体后运行或 `Build > Build APK(s)`。Compose 原型可请求新闻、展示词条与风险卡；持仓页面在后端认证接入后开放。

## CSV 导入格式

```csv
symbol,name,quantity,average_cost
600519,贵州茅台,100,1450.00
```

仅接受用户主动导出的 CSV；不要保存交易密码、短信验证码或券商会话 Cookie。

## 推荐集成

| 组件 | 用途 | 接入原则 |
| --- | --- | --- |
| [AKShare](https://github.com/akfamily/akshare) | A 股行情、公告等数据适配 | 逐数据源核对许可、稳定性和延迟。 |
| [OpenBB](https://github.com/OpenBB-finance/OpenBB) | 可扩展金融数据与分析平台 | 适合统一数据供应商，A 股覆盖需验证。 |
| [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) | 金融情绪、关系抽取研究基线 | 先用中文 A 股标注集评测，并加规则兜底。 |

第一阶段建议采用“可信新闻源 + 规则实体匹配 + 可复核证据”，不要从预测涨跌开始。

## 迭代路线

1. 第 1 周：持仓录入、关注清单、词条卡、新闻来源跳转。
2. 第 2–3 周：新闻去重、公司/行业关联、公告和事件提醒。
3. 第 4 周：关注偏好、风险暴露、每日报告；所有结论附来源和置信度。
4. 后续：合规评审后再接入付费行情、LLM 摘要、推送与回测。

详见 [当前 v3 架构设计](docs/ThirdHand_Architecture_v3_consolidated.md) 与
[当前 v3 路线图](docs/ThirdHand_v3_Roadmap_and_Ledger.md)。
