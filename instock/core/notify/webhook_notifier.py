#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用 Webhook 通知 - 适配 OpenClaw / 钉钉 / 飞书 / 自定义 Webhook
"""

import json
import logging
import requests
from .notifier import NotifyType

__author__ = 'Nice'
__date__ = '2026/04/29'


class WebhookNotifier:
    """
    通用 Webhook 通知器
    
    配置示例:
    {
        "type": "webhook",
        "name": "openclaw",
        "enabled": true,
        "url": "http://localhost:你的端口/webhook/stock-alert",
        "headers": {"Content-Type": "application/json"},
        "template": "openclaw"  // openclaw | dingtalk | feishu | custom
    }
    """
    
    def __init__(self, url, headers=None, name='webhook', template='openclaw'):
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}
        self.name = name
        self.template = template
    
    def send(self, notify_type: NotifyType, title: str, content: str, **kwargs):
        """发送 Webhook 通知"""
        payload = self._build_payload(notify_type, title, content, **kwargs)
        if payload is None:
            return
        
        try:
            resp = requests.post(
                self.url,
                headers=self.headers,
                json=payload,
                timeout=10
            )
            if resp.status_code == 200:
                logging.info(f"[通知-Webhook:{self.name}] 发送成功: {title}")
            else:
                logging.warning(f"[通知-Webhook:{self.name}] 发送失败: {resp.status_code} {resp.text}")
        except Exception as e:
            logging.error(f"[通知-Webhook:{self.name}] 请求异常: {e}")
    
    def _build_payload(self, notify_type, title, content, **kwargs):
        """根据模板构建不同平台的 payload"""
        
        if self.template == 'openclaw':
            # OpenClaw Webhook 格式
            return {
                "type": notify_type.value,
                "title": title,
                "content": content,
                "stocks": kwargs.get('stocks', []),
                "timestamp": kwargs.get('timestamp', '')
            }
        
        elif self.template == 'dingtalk':
            # 钉钉机器人
            return {
                "msgtype": "markdown",
                "markdown": {
                    "title": f"{notify_type.value} {title}",
                    "text": f"## {notify_type.value} {title}\n\n{content}"
                }
            }
        
        elif self.template == 'feishu':
            # 飞书机器人
            return {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {"tag": "plain_text", "content": f"{notify_type.value} {title}"}
                    },
                    "elements": [{
                        "tag": "markdown",
                        "content": content
                    }]
                }
            }
        
        else:
            # 自定义格式
            return {
                "notify_type": notify_type.value,
                "title": title,
                "content": content
            }
