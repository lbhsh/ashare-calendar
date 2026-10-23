# A股金融节点日历（可订阅 ICS）

补齐公开宏观日历通常订不到的 A 股专属节点：MSCI/中证调仓、两会、期权交割、财报截止、重要会议等。

## 文件

| 文件 | 说明 |
|------|------|
| `events.json` | 手工维护的节点 + 交割日生成规则 |
| `generate_ics.py` | 纯标准库生成 RFC5545 ICS |
| `ashare_events.ics` | 输出日历（可订阅） |

## 生成本地 ICS

```bash
cd /workspace/ashare-calendar   # 或你拷贝到的目录
python3 generate_ics.py
```

改完 `events.json` 再跑一次即可；同一事件 `id` 对应稳定 `UID`，重新订阅/刷新会就地更新，不会重复堆事件。

## 今日怎么订到手机（推荐路径）

本机 `/workspace` 里的文件手机访问不到，需要挂到一个 **HTTPS 静态 URL**。

### 方案 A：GitHub Pages（最省事）

1. 新建公开仓库，例如 `ashare-calendar`
2. 把本目录推上去（至少要有 `ashare_events.ics`）
3. Settings → Pages → Deploy from branch `main` / `/ (root)`
4. 订阅地址形如：

   `https://<你的用户名>.github.io/ashare-calendar/ashare_events.ics`

5. **iPhone**：设置 → 日历 → 账户 → 添加账户 → 其他 → 添加已订阅的日历 → 粘贴上面 URL  
   **Mac**：日历 → 文件 → 新建日历订阅 → 粘贴 URL

可选：用 GitHub Actions 每月跑一次 `python3 generate_ics.py` 并 commit，保持交割日与手工节点新鲜。

### 方案 B：QNAP NAS Web 共享

1. 把 `ashare_events.ics` 放到 QNAP 可公网/内网 HTTPS 访问的目录（Web Server、Container Station nginx、或 CloudLink）
2. 确保能用浏览器直接打开该 `.ics`（`Content-Type: text/calendar` 更佳，`text/plain` 通常也能订）
3. 在 iPhone/Mac 用该 URL 添加订阅

内网 URL 仅同一网络可用；出差要订，优先 Pages 或带外网映射的 NAS。

### 方案 C：临时本机试订

```bash
python3 -m http.server 8765 --directory .
# 同网段设备访问 http://<电脑局域网IP>:8765/ashare_events.ics
```

仅适合短测；手机日历长期订阅请用 A/B。

## 已含类别

- **[调仓]** MSCI 季度/半年度公布与生效；中证半年度调仓（6/12 月）
- **[两会]** 2026 政协/人大开闭幕；2027 窗口待公告
- **[交割]** ETF 期权第四个星期三；股指期/期权第三个星期五（节假日顺延需人工覆盖）
- **[财报]** 年报+一季报 4/30、半年报 8/31、三季报 10/31
- **[政策]** 已知全会等（如二十届五中全会）

**刻意少放** PMI/CPI/LPR：Finance Calendar 中国源已覆盖；本日历专注缺口节点。

## 待公告 / 近似日期

标题或说明含「待公告」的条目：

- 中证 2026-12、2027-06、2027-12 调仓（按「6/12 月第二个星期五」推算）
- 2027 两会开幕日
- 股指交割遇长假时，以交易所通知为准（示例：2026-06 端午顺延已写入覆盖项）

MSCI 日期来自 MSCI 公布的下一轮八次审议日程，官方保留变更权。

## 维护

1. 编辑 `events.json`（改日期、加节点、或在 `generators.*.skip_keys` / `overrides_generated` 处理节假日）
2. `python3 generate_ics.py`
3. 推送到 GitHub Pages 或拷到 NAS

OpenClaw / cron 示例：

```bash
0 8 1 * * cd /share/ashare-calendar && /usr/bin/python3 generate_ics.py
```
