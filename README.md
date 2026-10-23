# A股金融节点日历（可订阅 ICS）

补齐公开宏观日历通常订不到的 A 股专属节点：MSCI/中证调仓、两会、期权交割、财报截止、重要会议等。  
另附 **华尔街见闻宏观** 自动更新订阅（与手工节点分开两个 `.ics`）。

## 订阅地址（直接用）

| 日历 | URL |
|------|-----|
| **A 股节点（手工+规则）** | https://raw.githubusercontent.com/lbhsh/ashare-calendar/main/ashare_events.ics |
| **华尔街见闻宏观（自动）** | https://raw.githubusercontent.com/lbhsh/ashare-calendar/main/wscn_macro.ics |
| **东方财富财经日历（自动）** | https://raw.githubusercontent.com/lbhsh/ashare-calendar/main/eastmoney_calendar.ics |

**iPhone**：设置 → 日历 → 账户 → 添加账户 → 其他 → 添加已订阅的日历 → 粘贴 URL  
**Mac**：日历 → 文件 → 新建日历订阅 → 粘贴 URL

建议：宏观看见闻源；休市/补充宏观+重要会议看东方财富源；调仓/两会/交割看 A 股节点源。三份可一起订。

## 文件

| 文件 | 说明 |
|------|------|
| `events.json` | 手工维护的节点 + 交割日生成规则 |
| `generate_ics.py` | 纯标准库生成 `ashare_events.ics` |
| `ashare_events.ics` | A 股专属节点日历 |
| `fetch_wscn_macro.py` | 拉取华尔街见闻宏观 API → `wscn_macro.ics` |
| `wscn_macro.ics` | 宏观日历（GitHub Actions 每日刷新） |
| `fetch_eastmoney_calendar.py` | 拉取东方财富大事提醒 → `eastmoney_calendar.ics` |
| `eastmoney_calendar.ics` | 休市 + 筛选经济数据 + 重要会议（每日刷新） |
| `.github/workflows/update-wscn-macro.yml` | 见闻：每天北京时间约 08:30 |
| `.github/workflows/update-eastmoney-calendar.yml` | 东方财富：每天北京时间约 09:00 |

## 华尔街见闻宏观：数据源与筛选

- **API**：`https://api-one-wscn.awtmt.com/apiv1/finance/macrodatas?start=<unix>&end=<unix>`
- **窗口**：一次请求约 ≤28 天，脚本向前分段拉约 **90 天**
- **筛选**（写入 ICS 的规则）：
  - **中国 / 中国香港**（`country_id` ∈ `CN`, `HK`）：全部保留
  - **其他国家/地区**：仅保留 **重要性 ≥ 3**（见闻量表约 1–4，4 最高）
- **时区**：`Asia/Shanghai`（按 `public_date` 打点，时长 1 小时）
- **稳定 UID**：基于见闻事件 `id`，刷新不会重复堆事件

本地重拉：

```bash
python3 fetch_wscn_macro.py
```

## 东方财富财经日历：数据源与筛选

- **API（免登录）**：`https://data.eastmoney.com/dataapi/dcrl/dstx?fromdate=YYYY-MM-DD&todate=YYYY-MM-DD&option=xsap,jjsj,hyhy`
  - 对应页面：[大事提醒](https://data.eastmoney.com/dcrl/dashi.html)
  - `option` 代码：`xsap` 休市、`jjsj` 经济数据、`hyhy` 会议（另有 `xgsg`/`tfpxx`/`hsgg`/`nbjb`/`gddh` 等个股向类型，默认不拉）
- **补充接口（会议同源）**：`https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_CPH_FECALENDAR&...`（本仓库当前以 dstx 为准）
- **窗口**：回溯约 3 天 + 向前约 **90 天**
- **写入 ICS 的规则**：
  - **休市**：保留 A 股 / 港股 / 沪深股通 / 港股通
  - **经济数据**：去掉「库存」等噪音；中国/港澳需命中 CPI/PMI/LPR/GDP/社融 等关键词；海外同关键词
  - **会议**：仅美联储议息、中央全会，以及名称含两会/政治局/中央经济/G20 等
- **时区**：`Asia/Shanghai`；有钟点的数据用 1 小时块，休市/会议用全天
- **稳定 UID**：基于事件内容哈希，刷新不会重复堆事件

本地重拉：

```bash
python3 fetch_eastmoney_calendar.py
```

## 生成本地 A 股节点 ICS

```bash
python3 generate_ics.py
```

改完 `events.json` 再跑一次即可。

## 已含类别（ashare_events）

- **[调仓]** MSCI 季度/半年度公布与生效；中证半年度调仓（6/12 月）
- **[两会]** 2026 政协/人大开闭幕；2027 窗口待公告
- **[交割]** ETF 期权第四个星期三；股指期/期权第三个星期五（节假日顺延需人工覆盖）
- **[财报]** 年报+一季报 4/30、半年报 8/31、三季报 10/31
- **[政策]** 已知全会等（如二十届五中全会）

**刻意少放** PMI/CPI/LPR：见闻宏观 ICS 与 Finance Calendar 中国源已覆盖；`ashare_events` 专注缺口节点。

## 待公告 / 近似日期

标题或说明含「待公告」的条目：

- 中证 2026-12、2027-06、2027-12 调仓（按「6/12 月第二个星期五」推算）
- 2027 两会开幕日
- 股指交割遇长假时，以交易所通知为准（示例：2026-06 端午顺延已写入覆盖项）

MSCI 日期来自 MSCI 公布的下一轮八次审议日程，官方保留变更权。

## 维护

1. 编辑 `events.json` → `python3 generate_ics.py` → `git push`
2. 见闻 / 东方财富 ICS 一般不用手管；Actions 失败时可本地 `python3 fetch_wscn_macro.py` 或 `python3 fetch_eastmoney_calendar.py` 再推送
