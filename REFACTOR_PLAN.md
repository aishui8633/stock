# InStock 改造计划 - 股票监控+通知+交易系统

## 📐 当前架构分析

### 项目结构
```
instock/
├── bin/              # 启动脚本 (run_job.sh, run_web.sh, run_trade.bat)
├── config/           # 配置文件 (trade_client.json, proxy.txt, eastmoney_cookie.txt)
├── core/             # 核心引擎
│   ├── crawling/     # 数据爬虫 (东方财富/新浪接口) ← 数据源层
│   ├── strategy/     # 11个选股策略 (MACD/均线突破/海龟等)
│   ├── backtest/     # 回测引擎
│   ├── indicator/    # 技术指标 (TA-Lib)
│   ├── kline/        # K线形态识别 (61种)
│   ├── stockfetch.py # 统一数据获取入口
│   └── tablestructure.py  # 数据库表结构定义
├── job/              # 定时任务 (日级批量任务)
│   ├── execute_daily_job.py    # 主调度入口
│   ├── basic_data_daily_job.py # 基础数据抓取
│   ├── indicators_data_daily_job.py  # 指标计算
│   ├── strategy_data_daily_job.py    # 策略选股
│   └── backtest_data_daily_job.py    # 回测
├── lib/              # 公共库 (数据库/交易时间/加解密)
├── trade/            # 自动交易模块
│   ├── robot/        # 交易引擎 (基于 easytrader)
│   ├── strategies/   # 交易策略 (stratey1.py 示例)
│   └── trade_service.py  # 交易服务入口
└── web/              # Web UI (Tornado)
    ├── web_service.py    # Web 服务入口 (端口 9988)
    └── templates/        # 前端页面
```

### 数据流
```
东方财富API → stockfetch.py → job定时任务 → MySQL数据库 → Web展示/策略计算
```

### 交易流
```
策略引擎 → easytrader → 券商客户端(GUI) → 实际下单
```

### 当前限制
1. **日级任务**：数据在收盘后批量处理，盘中无实时监控
2. **无通知**：没有消息推送机制
3. **交易仅限 Windows**：easytrader 依赖 GUI 自动化
4. **策略固定**：选股策略硬编码，无法动态配置

---

## 🎯 改造目标

| 模块 | 当前 | 改造后 |
|------|------|--------|
| 行情监控 | 日级批量 | 盘中实时（每3-5分钟） |
| 通知推送 | 无 | QQ/微信/钉钉推送 |
| 交易执行 | easytrader + 广发 | easytrader + 同花顺 |
| 策略管理 | 硬编码 | 可配置 + OpenClaw cron 调度 |
| 部署 | Docker | NAS(Docker 监控) + Windows(交易) |

---

## 📋 改造计划

### Phase 1: 搭建监控+通知基础（优先级最高）

#### 1.1 新建通知模块 `instock/core/notify/`
```
instock/core/notify/
├── __init__.py
├── notifier.py       # 通知基类 + 路由
├── webhook_notifier.py  # Webhook 通用通知 (OpenClaw/钉钉/飞书)
├── qq_notifier.py    # QQ Bot 通知
└── wechat_notifier.py # 微信通知
```

**推送内容模板**：
- 🟢 选股信号：发现符合条件的股票列表
- 🔴 买卖信号：策略触发买入/卖出
- 📊 每日复盘：收盘后的策略统计
- ⚠️ 异常告警：系统异常/数据源失败

#### 1.2 新建盘中监控模块 `instock/monitor/`
```
instock/monitor/
├── __init__.py
├── monitor_service.py   # 监控服务主入口
├── realtime_fetcher.py  # 实时行情获取器
├── signal_engine.py     # 信号引擎（策略匹配）
└── config.json          # 监控配置（自选股列表、策略选择）
```

#### 1.3 OpenClaw 集成调度
- 用 `cron` 定时调用 Python 脚本检查信号
- 信号触发时通过 OpenClaw 的 `message` 工具推送

### Phase 2: 交易层改造

#### 2.1 修改 `instock/config/trade_client.json`
```json
{
  "user": "你的账号",
  "password": "你的密码",
  "exe_path": "C:/同花顺安装目录/xiadan.exe",
  "broker_type": "universal_client"
}
```

#### 2.2 改造交易策略
- 替换 `stratey1.py` 为自定义策略
- 策略接收信号引擎的买卖指令
- 加入风控（止损/仓位控制）

### Phase 3: 自选股管理

#### 3.1 Web UI 自选股页面
- 添加/删除自选股
- 设置每只股票的监控策略
- 设置价格/涨跌幅提醒阈值

#### 3.2 配置文件化
```json
{
  "watchlist": [
    {"code": "600519", "name": "贵州茅台", "strategies": ["breakthrough_platform", "turtle_trade"]},
    {"code": "000858", "name": "五粮液", "strategies": ["parking_apron"]}
  ],
  "alerts": [
    {"code": "600519", "type": "price_above", "value": 1800},
    {"code": "000858", "type": "pct_change", "value": -3.0}
  ]
}
```

---

## 🚀 部署架构

```
┌─────────────────────────────────────────────┐
│  NAS (Linux) - 监控+选股层                   │
│  ├── Docker: MariaDB (数据存储)              │
│  ├── Docker: InStock Web (Web UI :9988)     │
│  ├── OpenClaw cron (定时调度)               │
│  │   ├── 9:30  开盘数据初始化                │
│  │   ├── 每5min 实时监控+信号检测            │
│  │   ├── 15:00 收盘复盘报告                  │
│  └── 通知推送 → QQ/微信                      │
└──────────────────┬──────────────────────────┘
                   │ 信号传递
                   ▼
┌─────────────────────────────────────────────┐
│  Windows 机器 - 交易执行层                   │
│  ├── 同花顺客户端 (GUI)                      │
│  ├── easytrader (接收信号自动下单)           │
│  └── 策略确认层 (可设人工确认)               │
└─────────────────────────────────────────────┘
```

---

## 📝 实施顺序

1. ✅ Fork 项目 → `aishui8633/stock` (已完成)
2. ✅ 克隆到本地工作区 (已完成)
3. 🔲 创建通知模块 + OpenClaw 推送接口
4. 🔲 创建盘中实时监控脚本（基于东方财富实时接口）
5. 🔲 集成 OpenClaw cron 调度
6. 🔲 Docker 部署测试
7. 🔲 自定义交易策略
8. 🔲 Windows 交易层对接同花顺

---

## ⚡ 快速启动（当前阶段）

先做第3-5步，实现**监控+通知**，交易部分后续再加。
