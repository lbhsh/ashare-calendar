# A股重要节点日历（可订阅 ICS）

**只订这一份就够了。** 专收 A 股最关键节点，刻意砍掉全球宏观噪音。

## 主订阅（推荐唯一订阅）

https://raw.githubusercontent.com/lbhsh/ashare-calendar/main/ashare_important.ics

**iPhone**：设置 → 日历 → 账户 → 添加账户 → 其他 → 添加已订阅的日历 → 粘贴上面 URL  
**Mac**：日历 → 文件 → 新建日历订阅 → 粘贴 URL

GitHub Actions 每天北京时间约 **08:40** 自动刷新宏观部分。

## 这份里有什么

| 类别 | 内容 | 来源 |
|------|------|------|
| **[调仓]** | MSCI / 中证指数调仓公布与生效 | `events.json` 手工 |
| **[两会]/[政策]** | 两会开闭幕、中央全会等 | 手工 |
| **[交割]** | ETF 期权第四个周三；股指期/期权第三个周五 | 规则生成 |
| **[财报]** | 年报+一季报 4/30、半年报 8/31、三季报 10/31 | 手工 |
| **[宏观]** | 中国高影响：官方 PMI、CPI/PPI、LPR、GDP、社融、新增人民币贷款 | 华尔街见闻 API（严格关键词） |
| **[宏观]** | 可选外溢：仅 FOMC / 美联储利率决议 | 见闻 API（有则写入） |

当前体量大约：**手工节点 ~80 条（跨约两年）+ 未来约 90 天内个位数～十几条宏观**，不会上百条全球刷屏。

## 刻意不放

- 全球非农 / PCE / ISM / 各国利率决议（除 FOMC）
- RatingDog / 财新 PMI、外汇储备、进出口细项、库存、展会论坛
- 休市琐碎、个股解禁/公告
- 东方财富 / 见闻「全量」宏观

## 本地重建

```bash
python3 build_ashare_important.py   # → ashare_important.ics
python3 generate_ics.py             # 仅重建手工节点 ashare_events.ics（可选）
```

改调仓/两会/财报日期：编辑 `events.json` → 跑上面两条 → `git push`。

## 文件

| 文件 | 说明 |
|------|------|
| **`ashare_important.ics`** | **主订阅**（请只用这个） |
| `build_ashare_important.py` | 合并手工节点 + 严格中国宏观 |
| `events.json` / `generate_ics.py` | 手工节点与交割规则 |
| `ashare_events.ics` | 仅手工节点（legacy / 对照） |
| `fetch_wscn_macro.py` / `wscn_macro.ics` | 见闻宽口径（legacy，默认不自动更新） |
| `fetch_eastmoney_calendar.py` / `eastmoney_calendar.ics` | 东财宽口径（legacy，默认不自动更新） |
| `.github/workflows/update-ashare-important.yml` | 每日刷新主订阅 |

## Legacy 订阅（一般不用）

若仍想看宽口径宏观，可手动跑 Actions 或本地脚本后订阅：

- https://raw.githubusercontent.com/lbhsh/ashare-calendar/main/ashare_events.ics
- https://raw.githubusercontent.com/lbhsh/ashare-calendar/main/wscn_macro.ics
- https://raw.githubusercontent.com/lbhsh/ashare-calendar/main/eastmoney_calendar.ics

**建议取消这些订阅，只保留 `ashare_important.ics`。**

## 待公告说明

标题含「待公告」的：中证部分调仓日、2027 两会等，以官方公告为准。股指交割遇长假以交易所通知为准。
