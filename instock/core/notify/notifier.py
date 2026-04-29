#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通知路由模块 - 统一管理所有通知渠道
"""

import logging
import os
import json
from enum import Enum

__author__ = 'Nice'
__date__ = '2026/04/29'


class NotifyType(Enum):
    """通知类型"""
    SELECTION = "🟢 选股信号"       # 发现符合条件的股票
    BUY = "🔴 买入信号"            # 策略触发买入
    SELL = "🔵 卖出信号"           # 策略触发卖出
    DAILY_REPORT = "📊 每日复盘"   # 收盘复盘报告
    ALERT = "⚠️ 异常告警"          # 系统异常
    PRICE_ALERT = "💰 价格提醒"    # 价格触及阈值


class Notifier:
    """
    通知路由器 - 根据配置将消息推送到不同渠道
    
    支持渠道:
    - webhook: 通用 Webhook (OpenClaw/钉钉/飞书)
    - qq: QQ Bot
    - wechat: 微信通知
    """
    
    _instance = None
    _channels = []
    
    def __new__(cls, config_path=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            if config_path:
                cls._instance._load_config(config_path)
            else:
                # 默认配置路径
                cpath_current = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                default_config = os.path.join(cpath_current, 'config', 'notify.json')
                if os.path.exists(default_config):
                    cls._instance._load_config(default_config)
        return cls._instance
    
    def _load_config(self, config_path):
        """加载通知配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            channels = config.get('channels', [])
            for ch in channels:
                channel_type = ch.get('type', '')
                enabled = ch.get('enabled', True)
                if not enabled:
                    continue
                
                if channel_type == 'webhook':
                    from .webhook_notifier import WebhookNotifier
                    self._channels.append(WebhookNotifier(
                        url=ch.get('url', ''),
                        headers=ch.get('headers', {}),
                        name=ch.get('name', 'webhook')
                    ))
                elif channel_type == 'qq':
                    from .qq_notifier import QQNotifier
                    self._channels.append(QQNotifier(
                        user_id=ch.get('user_id', ''),
                        group_id=ch.get('group_id', ''),
                        name=ch.get('name', 'qq')
                    ))
                elif channel_type == 'wechat':
                    from .wechat_notifier import WechatNotifier
                    self._channels.append(WechatNotifier(
                        corp_id=ch.get('corp_id', ''),
                        agent_id=ch.get('agent_id', ''),
                        secret=ch.get('secret', ''),
                        name=ch.get('name', 'wechat')
                    ))
            
            logging.info(f"[通知] 加载了 {len(self._channels)} 个通知渠道")
        except Exception as e:
            logging.error(f"[通知] 加载配置失败: {e}")
    
    def send(self, notify_type: NotifyType, title: str, content: str, **kwargs):
        """
        发送通知到所有已配置的渠道
        
        Args:
            notify_type: 通知类型
            title: 标题
            content: 内容 (支持 markdown)
            **kwargs: 额外参数 (如 stocks 列表)
        """
        if not self._channels:
            logging.info(f"[通知] 没有配置通知渠道，跳过推送: {title}")
            # 降级: 打印到控制台
            print(f"[通知] {notify_type.value} - {title}")
            print(content)
            return
        
        for channel in self._channels:
            try:
                channel.send(notify_type, title, content, **kwargs)
            except Exception as e:
                logging.error(f"[通知] {channel.name} 发送失败: {e}")
