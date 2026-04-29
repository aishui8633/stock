#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QQ 通知器 - 通过 OpenClaw QQ Bot 推送
"""

import logging
from .notifier import NotifyType

__author__ = 'Nice'
__date__ = '2026/04/29'


class QQNotifier:
    """
    QQ 通知器
    
    注意: 此模块需要通过 OpenClaw 的 message 工具推送
    实际使用时由 OpenClaw cron 任务或外部脚本调用
    这里提供消息格式化能力
    
    配置示例:
    {
        "type": "qq",
        "name": "qq_main",
        "enabled": true,
        "user_id": "user_openid",
        "group_id": "group_openid"
    }
    """
    
    def __init__(self, user_id='', group_id='', name='qq'):
        self.user_id = user_id
        self.group_id = group_id
        self.name = name
    
    def send(self, notify_type: NotifyType, title: str, content: str, **kwargs):
        """
        格式化 QQ 通知消息
        
        实际发送由外部调用方完成（OpenClaw cron 或独立脚本）
        这里返回格式化后的消息文本
        """
        message = self._format_message(notify_type, title, content, **kwargs)
        
        # 如果有 stocks 列表，追加详情
        stocks = kwargs.get('stocks', [])
        if stocks:
            stock_lines = self._format_stocks(stocks)
            message += "\n\n" + stock_lines
        
        # 实际发送逻辑（需要 OpenClaw 环境）
        # 通过写入文件的方式让 OpenClaw 读取并发送
        self._write_to_queue(message)
        
        logging.info(f"[通知-QQ:{self.name}] 消息已加入队列: {title}")
        return message
    
    def _format_message(self, notify_type, title, content, **kwargs):
        """格式化 QQ 消息文本"""
        emoji_map = {
            NotifyType.SELECTION: "🟢",
            NotifyType.BUY: "🔴",
            NotifyType.SELL: "🔵",
            NotifyType.DAILY_REPORT: "📊",
            NotifyType.ALERT: "⚠️",
            NotifyType.PRICE_ALERT: "💰"
        }
        emoji = emoji_map.get(notify_type, "📢")
        
        return f"{emoji} {title}\n{content}"
    
    def _format_stocks(self, stocks):
        """格式化股票列表"""
        lines = ["---", "📋 股票详情:"]
        for s in stocks:
            code = s.get('code', '')
            name = s.get('name', '')
            price = s.get('price', '-')
            change = s.get('change', '')
            reason = s.get('reason', '')
            
            change_str = f" ({change})" if change else ""
            line = f"  • {name}({code}) {price}{change_str}"
            if reason:
                line += f" | {reason}"
            lines.append(line)
        return "\n".join(lines)
    
    def _write_to_queue(self, message):
        """
        写入消息队列文件，等待 OpenClaw 读取发送
        
        文件路径: instock/notify_queue.json
        格式: [{"time": "...", "target": "...", "message": "..."}]
        """
        import json
        import os
        from datetime import datetime
        
        cpath_current = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        queue_path = os.path.join(cpath_current, 'notify_queue.json')
        
        queue = []
        if os.path.exists(queue_path):
            try:
                with open(queue_path, 'r', encoding='utf-8') as f:
                    queue = json.load(f)
            except:
                queue = []
        
        queue.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "target": self.group_id or self.user_id,
            "message": message
        })
        
        # 只保留最近 50 条
        queue = queue[-50:]
        
        with open(queue_path, 'w', encoding='utf-8') as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
