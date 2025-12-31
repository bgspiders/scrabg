"""
哈希工具：用于计算链接和内容的哈希值，实现去重功能
"""
import hashlib
from typing import Optional


class HashHelper:
    """哈希计算工具，支持 MD5 和 SHA256"""
    
    @staticmethod
    def md5(text: str) -> str:
        """
        计算文本的 MD5 哈希值
        
        Args:
            text: 待哈希的文本
            
        Returns:
            MD5 哈希值（十六进制字符串）
        """
        if not text:
            return ""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    @staticmethod
    def sha256(text: str) -> str:
        """
        计算文本的 SHA256 哈希值
        
        Args:
            text: 待哈希的文本
            
        Returns:
            SHA256 哈希值（十六进制字符串）
        """
        if not text:
            return ""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    @staticmethod
    def get_link_hash(link: str) -> str:
        """
        获取链接的哈希值，用于去重判断
        
        Args:
            link: 文章链接
            
        Returns:
            链接的 MD5 哈希值
        """
        return HashHelper.md5(link) if link else ""
    
    @staticmethod
    def get_content_hash(content: str) -> str:
        """
        获取内容的哈希值，用于去重判断
        
        Args:
            content: 文章内容
            
        Returns:
            内容的 SHA256 哈希值（防止哈希碰撞）
        """
        return HashHelper.sha256(content) if content else ""
