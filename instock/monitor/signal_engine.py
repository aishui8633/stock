#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
信号引擎 - 根据策略规则检测买卖信号
"""

import logging
import pandas as pd
import os
import json
from datetime import datetime

__author__ = 'Nice'
__date__ = '2026/04/29'


class SignalEngine:
    """
    信号引擎 - 检测股票是否触发策略信号
    
    支持信号类型:
    1. 价格突破: 突破支撑/压力位
    2. 涨跌幅: 达到设定的涨跌幅阈值
    3. 成交量异常: 量比超过阈值
    4. 策略匹配: 匹配内置选股策略（需要历史数据）
    """
    
    def __init__(self, config_path=None):
        self.config = self._load_config(config_path)
        self.watchlist = self.config.get('watchlist', [])
        self.alerts = self.config.get('alerts', [])
        self.strategies = self.config.get('strategies', [])
        self._fired_alerts = set()  # 已触发的告警ID（防重复）
    
    def _load_config(self, config_path):
        """加载监控配置"""
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # 默认配置路径
        default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
        if os.path.exists(default_path):
            with open(default_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return {}
    
    def check_alerts(self, quotes: pd.DataFrame):
        """
        检查所有告警规则
        
        Args:
            quotes: 实时行情 DataFrame
        
        Returns:
            list 触发的信号列表 [{"code": "", "name": "", "type": "", "message": "", "data": {}}]
        """
        signals = []
        
        for alert in self.alerts:
            code = alert.get('code', '')
            alert_type = alert.get('type', '')
            
            # 获取该股票的行情
            stock_quote = quotes[quotes['code'] == code]
            if stock_quote.empty:
                continue
            
            stock = stock_quote.iloc[0]
            alert_id = f"{code}_{alert_type}"
            
            # 防重复触发检查
            if alert_id in self._fired_alerts:
                continue
            
            signal = None
            
            if alert_type == 'price_above':
                threshold = alert.get('value', 0)
                if stock['price'] >= threshold:
                    signal = {
                        'type': 'price_alert',
                        'code': code,
                        'name': stock['name'],
                        'message': f"{stock['name']}({code}) 价格突破 {threshold}，当前 {stock['price']}",
                        'data': stock.to_dict()
                    }
            
            elif alert_type == 'price_below':
                threshold = alert.get('value', 0)
                if stock['price'] <= threshold:
                    signal = {
                        'type': 'price_alert',
                        'code': code,
                        'name': stock['name'],
                        'message': f"{stock['name']}({code}) 价格跌破 {threshold}，当前 {stock['price']}",
                        'data': stock.to_dict()
                    }
            
            elif alert_type == 'pct_change_above':
                threshold = alert.get('value', 0)
                if stock['change_pct'] >= threshold:
                    signal = {
                        'type': 'price_alert',
                        'code': code,
                        'name': stock['name'],
                        'message': f"{stock['name']}({code}) 涨幅超过 {threshold}%，当前 {stock['change_pct']}%",
                        'data': stock.to_dict()
                    }
            
            elif alert_type == 'pct_change_below':
                threshold = alert.get('value', 0)
                if stock['change_pct'] <= threshold:
                    signal = {
                        'type': 'price_alert',
                        'code': code,
                        'name': stock['name'],
                        'message': f"{stock['name']}({code}) 跌幅超过 {abs(threshold)}%，当前 {stock['change_pct']}%",
                        'data': stock.to_dict()
                    }
            
            elif alert_type == 'volume_surge':
                threshold = alert.get('value', 2.0)  # 默认量比>2
                if stock['volume_ratio'] >= threshold:
                    signal = {
                        'type': 'price_alert',
                        'code': code,
                        'name': stock['name'],
                        'message': f"{stock['name']}({code}) 量比异常 {stock['volume_ratio']}x，可能有大单",
                        'data': stock.to_dict()
                    }
            
            elif alert_type in ('cost_profit_pct', 'cost_loss_pct'):
                # 基于成本价的盈亏告警
                cost = self._get_cost_price(code)
                if cost is None or cost <= 0:
                    continue
                current_price = stock['price']
                profit_pct = (current_price - cost) / cost * 100
                threshold = alert.get('value', 3.0)
                
                if alert_type == 'cost_profit_pct' and profit_pct >= threshold:
                    signal = {
                        'type': 'cost_alert',
                        'code': code,
                        'name': stock['name'],
                        'message': f"📈 {stock['name']}({code}) 盈利达 {profit_pct:+.2f}% (成本 {cost:.3f} → 现价 {current_price:.2f})，已超过阈值 {threshold}%",
                        'data': {**stock.to_dict(), 'cost': cost, 'profit_pct': round(profit_pct, 2)}
                    }
                elif alert_type == 'cost_loss_pct' and profit_pct <= threshold:
                    signal = {
                        'type': 'cost_alert',
                        'code': code,
                        'name': stock['name'],
                        'message': f"📉 {stock['name']}({code}) 亏损达 {profit_pct:+.2f}% (成本 {cost:.3f} → 现价 {current_price:.2f})，已超过阈值 {threshold}%",
                        'data': {**stock.to_dict(), 'cost': cost, 'profit_pct': round(profit_pct, 2)}
                    }
            
            if signal:
                signals.append(signal)
                self._fired_alerts.add(alert_id)
                logging.info(f"[信号] 触发: {signal['message']}")
        
        return signals
    
    def check_selection_strategies(self, quotes: pd.DataFrame):
        """
        基于内置策略筛选股票
        
        Args:
            quotes: 实时行情 DataFrame
        
        Returns:
            list 筛选结果 [{"code": "", "name": "", "strategy": "", "reason": "", "data": {}}]
        """
        results = []
        
        for strategy in self.strategies:
            strat_name = strategy.get('name', '')
            condition = strategy.get('condition', {})
            
            filtered = self._apply_condition(quotes, condition)
            
            for _, stock in filtered.iterrows():
                results.append({
                    'code': stock['code'],
                    'name': stock['name'],
                    'strategy': strat_name,
                    'reason': self._format_reason(condition, stock),
                    'data': stock.to_dict()
                })
        
        return results
    
    def _apply_condition(self, quotes: pd.DataFrame, condition: dict) -> pd.DataFrame:
        """应用筛选条件"""
        filtered = quotes.copy()
        
        # 涨跌幅筛选
        if 'change_pct_min' in condition:
            filtered = filtered[filtered['change_pct'] >= condition['change_pct_min']]
        if 'change_pct_max' in condition:
            filtered = filtered[filtered['change_pct'] <= condition['change_pct_max']]
        
        # 价格范围
        if 'price_min' in condition:
            filtered = filtered[filtered['price'] >= condition['price_min']]
        if 'price_max' in condition:
            filtered = filtered[filtered['price'] <= condition['price_max']]
        
        # 量比
        if 'volume_ratio_min' in condition:
            filtered = filtered[filtered['volume_ratio'] >= condition['volume_ratio_min']]
        
        # 换手率
        if 'turnover_min' in condition:
            filtered = filtered[filtered['turnover'] >= condition['turnover_min']]
        
        # 成交额
        if 'amount_min' in condition:
            filtered = filtered[filtered['amount'] >= condition['amount_min']]
        
        # 排除 ST
        if condition.get('exclude_st', True):
            filtered = filtered[~filtered['name'].str.contains('ST', na=False)]
        
        return filtered
    
    def _format_reason(self, condition, stock):
        """格式化筛选原因"""
        reasons = []
        
        if 'change_pct_min' in condition:
            reasons.append(f"涨幅≥{condition['change_pct_min']}%")
        if 'change_pct_max' in condition:
            reasons.append(f"涨幅≤{condition['change_pct_max']}%")
        if 'volume_ratio_min' in condition:
            reasons.append(f"量比≥{condition['volume_ratio_min']}")
        if 'turnover_min' in condition:
            reasons.append(f"换手率≥{condition['turnover_min']}%")
        if 'amount_min' in condition:
            reasons.append(f"成交额≥{condition['amount_min']/10000:.0f}万")
        
        return " | ".join(reasons)
    
    def _get_cost_price(self, code):
        """从自选股列表中获取成本价"""
        for item in self.watchlist:
            if item.get('code') == code and 'cost' in item:
                return float(item['cost'])
        return None
    
    def reset_fired_alerts(self):
        """重置已触发告警记录（每日收盘后调用）"""
        self._fired_alerts.clear()
