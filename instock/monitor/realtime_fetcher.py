#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时行情获取器 - 基于东方财富API获取盘中实时数据
"""

import logging
import requests
import pandas as pd
from datetime import datetime

__author__ = 'Nice'
__date__ = '2026/04/29'

# 东方财富实时行情API
EASTMONEY_REALTIME_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"


class RealtimeFetcher:
    """
    盘中实时行情获取器
    
    特点:
    - 直接调用东方财富API，无需数据库
    - 支持批量获取多只股票实时数据
    - 返回 DataFrame 格式，方便策略计算
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://quote.eastmoney.com/'
        })
    
    def get_stock_quote(self, codes):
        """
        获取多只股票实时行情
        
        Args:
            codes: 股票代码列表，如 ['600519', '000858']
        
        Returns:
            DataFrame 包含: code, name, price, change_pct, volume, amount, ...
        """
        if not codes:
            return pd.DataFrame()
        
        # 构建 secid 列表: 1.600519 (沪市), 0.000858 (深市)
        secids = []
        for code in codes:
            if code.startswith(('6', '9')):
                secids.append(f"1.{code}")
            else:
                secids.append(f"0.{code}")
        
        params = {
            'fltt': '2',
            'fields': 'f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18',
            'secids': ','.join(secids)
        }
        
        try:
            resp = self.session.get(EASTMONEY_REALTIME_URL, params=params, timeout=10)
            data = resp.json()
            
            if not data.get('data', {}).get('diff'):
                return pd.DataFrame()
            
            items = data['data']['diff']
            return self._parse_items(items)
        except Exception as e:
            logging.error(f"[实时行情] 获取失败: {e}")
            return pd.DataFrame()
    
    def get_all_spot(self):
        """
        获取全市场实时行情快照（沪深A股）
        
        Returns:
            DataFrame 全市场行情
        """
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            'pn': '1',
            'np': '1',
            'fltt': '2',
            'invt': '2',
            'fid': 'f3',
            'po': '1',
            'pz': '5000',  # 一次性获取全部
            'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048',
            'fields': 'f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18'
        }
        
        try:
            resp = self.session.get(url, params=params, timeout=15)
            data = resp.json()
            
            if not data.get('data', {}).get('diff'):
                return pd.DataFrame()
            
            items = data['data']['diff']
            return self._parse_items(items)
        except Exception as e:
            logging.error(f"[实时行情] 全市场快照失败: {e}")
            return pd.DataFrame()
    
    def _parse_items(self, items):
        """解析东方财富API返回的数据"""
        rows = []
        for item in items:
            code = str(item.get('f12', ''))
            row = {
                'code': code,
                'name': item.get('f14', ''),
                'price': item.get('f2'),          # 最新价
                'change_pct': item.get('f3'),      # 涨跌幅(%)
                'change': item.get('f4'),          # 涨跌额
                'volume': item.get('f5'),          # 成交量(手)
                'amount': item.get('f6'),          # 成交额
                'amplitude': item.get('f7'),       # 振幅(%)
                'turnover': item.get('f8'),        # 换手率(%)
                'pe_ratio': item.get('f9'),        # 市盈率(动态)
                'volume_ratio': item.get('f10'),   # 量比
                'high': item.get('f15'),           # 最高
                'low': item.get('f16'),            # 最低
                'open': item.get('f17'),           # 今开
                'prev_close': item.get('f18'),     # 昨收
                'market_id': item.get('f13'),      # 市场代码
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            rows.append(row)
        
        return pd.DataFrame(rows)
