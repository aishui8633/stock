#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信企业通知 - 企业微信应用消息
"""

import logging
import requests
from .notifier import NotifyType

__author__ = 'Nice'
__date__ = '2026/04/29'


class WechatNotifier:
    """
    企业微信应用通知
    
    配置示例:
    {
        "type": "wechat",
        "name": "wechat_work",
        "enabled": true,
        "corp_id": "你的企业ID",
        "agent_id": 1000001,
        "secret": "应用Secret"
    }
    """
    
    TOKEN_URL = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
    SEND_URL = "https://qyapi.weixin.qq.com/cgi-bin/message/send"
    
    def __init__(self, corp_id, agent_id, secret, name='wechat'):
        self.corp_id = corp_id
        self.agent_id = agent_id
        self.secret = secret
        self.name = name
        self._token = None
    
    def _get_token(self):
        """获取 access_token"""
        if self._token:
            return self._token
        
        try:
            resp = requests.get(self.TOKEN_URL, params={
                "corpid": self.corp_id,
                "corpsecret": self.secret
            }, timeout=10)
            data = resp.json()
            if data.get("errcode") == 0:
                self._token = data.get("access_token")
                return self._token
            else:
                logging.error(f"[通知-微信:{self.name}] 获取Token失败: {data}")
        except Exception as e:
            logging.error(f"[通知-微信:{self.name}] Token请求异常: {e}")
        return None
    
    def send(self, notify_type: NotifyType, title: str, content: str, **kwargs):
        """发送企业微信通知"""
        token = self._get_token()
        if not token:
            logging.error(f"[通知-微信:{self.name}] 无可用Token，跳过发送")
            return
        
        # 构建 markdown 消息
        markdown_content = f"## {notify_type.value} {title}\n\n{content}"
        
        stocks = kwargs.get('stocks', [])
        if stocks:
            stock_lines = []
            for s in stocks:
                code = s.get('code', '')
                name = s.get('name', '')
                price = s.get('price', '-')
                change = s.get('change', '')
                change_str = f" ({change})" if change else ""
                stock_lines.append(f"- **{name}**({code}): {price}{change_str}")
            markdown_content += "\n\n---\n📋 **股票详情**\n" + "\n".join(stock_lines)
        
        payload = {
            "touser": "@all",
            "msgtype": "markdown",
            "agentid": self.agent_id,
            "markdown": {"content": markdown_content}
        }
        
        try:
            resp = requests.post(
                f"{self.SEND_URL}?access_token={token}",
                json=payload,
                timeout=10
            )
            data = resp.json()
            if data.get("errcode") == 0:
                logging.info(f"[通知-微信:{self.name}] 发送成功: {title}")
            else:
                logging.warning(f"[通知-微信:{self.name}] 发送失败: {data}")
        except Exception as e:
            logging.error(f"[通知-微信:{self.name}] 请求异常: {e}")
