#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控服务主入口 - 可被 OpenClaw cron 调用的监控脚本

使用方式:
    # 单次检查（适合 cron 定时调用）
    python monitor_service.py --check
    
    # 持续监控模式（盘中运行）
    python monitor_service.py --daemon --interval 300
    
    # 查看自选股行情
    python monitor_service.py --watchlist
"""

import os
import sys
import json
import logging
import argparse
import time
from datetime import datetime, timedelta

# 添加项目路径
cpath_current = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)

from instock.monitor.realtime_fetcher import RealtimeFetcher
from instock.monitor.signal_engine import SignalEngine
from instock.core.notify.notifier import Notifier, NotifyType

__author__ = 'Nice'
__date__ = '2026/04/29'

# 交易时间检查
def is_trading_time():
    """检查当前是否在A股交易时间内"""
    now = datetime.now()
    # 周一到周五
    if now.weekday() >= 5:
        return False
    
    # 上午 9:30-11:30, 下午 13:00-15:00
    morning_start = now.replace(hour=9, minute=30, second=0)
    morning_end = now.replace(hour=11, minute=30, second=0)
    afternoon_start = now.replace(hour=13, minute=0, second=0)
    afternoon_end = now.replace(hour=15, minute=0, second=0)
    
    return (morning_start <= now <= morning_end) or (afternoon_start <= now <= afternoon_end)


def is_pre_market():
    """盘前（9:15-9:25 集合竞价）"""
    now = datetime.now()
    pre_start = now.replace(hour=9, minute=15, second=0)
    pre_end = now.replace(hour=9, minute=25, second=0)
    return pre_start <= now <= pre_end


def check_signals(config_path=None, output_format='text'):
    """
    执行单次信号检查
    
    Args:
        config_path: 配置文件路径
        output_format: 'text' | 'json' (用于OpenClaw读取)
    
    Returns:
        信号列表
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    # 初始化
    fetcher = RealtimeFetcher()
    engine = SignalEngine(config_path)
    notifier = Notifier(config_path)
    
    # 获取自选股列表
    watchlist = engine.watchlist
    if not watchlist:
        logging.warning("没有配置自选股，跳过监控")
        return []
    
    codes = [s.get('code', '') for s in watchlist if s.get('code')]
    logging.info(f"[监控] 开始检查 {len(codes)} 只自选股: {', '.join(codes[:5])}...")
    
    # 获取实时行情
    quotes = fetcher.get_stock_quote(codes)
    if quotes.empty:
        logging.error("[监控] 获取行情失败")
        return []
    
    logging.info(f"[监控] 获取到 {len(quotes)} 只股票行情")
    
    # 检查告警
    alert_signals = engine.check_alerts(quotes)
    
    # 检查策略筛选
    selection_signals = engine.check_selection_strategies(quotes)
    
    all_signals = alert_signals + selection_signals
    
    # 发送通知
    if alert_signals:
        stocks_data = [s['data'] for s in alert_signals]
        for signal in alert_signals:
            notifier.send(
                NotifyType.PRICE_ALERT,
                f"{signal['name']} 告警",
                signal['message'],
                stocks=[signal['data']]
            )
    
    if selection_signals:
        stocks_data = []
        for s in selection_signals:
            stocks_data.append({
                'code': s['code'],
                'name': s['name'],
                'price': s['data'].get('price', '-'),
                'change': f"{s['data'].get('change_pct', 0):.2f}%",
                'strategy': s['strategy'],
                'reason': s['reason']
            })
        
        content = f"发现 {len(selection_signals)} 只符合策略条件的股票"
        notifier.send(
            NotifyType.SELECTION,
            "选股信号",
            content,
            stocks=stocks_data
        )
    
    # 输出结果
    if output_format == 'json':
        print(json.dumps({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "quotes_count": len(quotes),
            "alert_signals": len(alert_signals),
            "selection_signals": len(selection_signals),
            "alerts": [{"code": s['code'], "name": s['name'], "message": s['message']} for s in alert_signals],
            "selections": [{"code": s['code'], "name": s['name'], "strategy": s['strategy'], "reason": s['reason']} for s in selection_signals]
        }, ensure_ascii=False))
    else:
        if all_signals:
            print(f"\n{'='*50}")
            print(f"📈 股票监控报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            print(f"{'='*50}")
            
            for signal in all_signals:
                msg = signal.get('message', '') or f"{signal.get('name', '')}({signal.get('code', '')}) 策略:{signal.get('strategy', '')} 原因:{signal.get('reason', '')}"
                print(f"\n{signal.get('type', 'signal')}: {msg}")
            
            print(f"\n共 {len(all_signals)} 个信号")
        else:
            print(f"\n✅ 无触发信号 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    return all_signals


def daemon_mode(config_path=None, interval=300):
    """
    持续监控模式
    
    Args:
        config_path: 配置文件路径
        interval: 检查间隔（秒），默认300秒（5分钟）
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(cpath_current, 'log', 'monitor.log')),
            logging.StreamHandler()
        ]
    )
    
    logging.info(f"[监控] 启动持续监控模式，间隔 {interval}s")
    
    while True:
        if is_trading_time():
            try:
                check_signals(config_path)
            except Exception as e:
                logging.error(f"[监控] 检查异常: {e}")
        else:
            logging.info(f"[监控] 非交易时间，跳过")
        
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description='InStock 股票监控服务')
    parser.add_argument('--check', action='store_true', help='执行单次信号检查')
    parser.add_argument('--daemon', action='store_true', help='持续监控模式')
    parser.add_argument('--watchlist', action='store_true', help='查看自选股行情')
    parser.add_argument('--interval', type=int, default=300, help='检查间隔（秒），默认300')
    parser.add_argument('--config', type=str, default=None, help='配置文件路径')
    parser.add_argument('--json', action='store_true', help='JSON格式输出')
    
    args = parser.parse_args()
    
    if args.check:
        output = 'json' if args.json else 'text'
        check_signals(args.config, output)
    
    elif args.daemon:
        daemon_mode(args.config, args.interval)
    
    elif args.watchlist:
        fetcher = RealtimeFetcher()
        engine = SignalEngine(args.config)
        codes = [s.get('code', '') for s in engine.watchlist if s.get('code')]
        
        if not codes:
            print("没有配置自选股")
            return
        
        quotes = fetcher.get_stock_quote(codes)
        if quotes.empty:
            print("获取行情失败")
            return
        
        print(f"\n{'='*85}")
        print(f"📋 自选股行情 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*85}")
        print(f"{'代码':<8} {'名称':<10} {'最新价':<8} {'涨跌幅%':<8} {'成本价':<8} {'盈亏%':<8} {'成交额(万)':<12} {'量比':<6}")
        print(f"{'-'*85}")
        
        for _, q in quotes.iterrows():
            code = q['code']
            amount_wan = q['amount'] / 10000 if q['amount'] else 0
            cost = next((s.get('cost') for s in engine.watchlist if s.get('code') == code), None)
            if cost:
                profit_pct = (q['price'] - cost) / cost * 100
                profit_str = f"{profit_pct:+.2f}"
            else:
                profit_str = "-"
            cost_str = f"{cost:.3f}" if cost else "-"
            print(f"{code:<8} {q['name']:<10} {q['price']:<8} {q['change_pct']:<8.2f} {cost_str:<8} {profit_str:<8} {amount_wan:<12.0f} {q['volume_ratio']:<6.2f}")
        
        print(f"{'='*85}")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
