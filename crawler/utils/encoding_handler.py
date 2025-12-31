"""
编码处理工具模块
自动识别响应编码，并正确处理不同编码的内容
"""

import re
import chardet
from typing import Tuple, Optional


class EncodingHandler:
    """响应编码处理器"""
    
    # 常见编码别名映射
    ENCODING_ALIASES = {
        'utf8': 'utf-8',
        'utf_8': 'utf-8',
        'gb2312': 'gb2312',
        'gbk': 'gbk',
        'big5': 'big5',
        'big5hkscs': 'big5',
        'iso8859-1': 'iso-8859-1',
        'latin1': 'iso-8859-1',
    }
    
    @staticmethod
    def detect_encoding(content: bytes, headers: dict = None) -> Tuple[str, float]:
        """
        自动检测内容编码
        
        Args:
            content: 二进制响应内容
            headers: 响应头字典（可选）
        
        Returns:
            Tuple[编码名称, 置信度] 如 ('utf-8', 0.99)
        """
        encoding = None
        confidence = 0.0
        
        # 1. 优先从响应头 Content-Type 中获取
        if headers:
            encoding = EncodingHandler._extract_encoding_from_headers(headers)
            if encoding:
                return encoding, 1.0
        
        # 2. 从 HTML meta 标签中提取编码
        encoding = EncodingHandler._extract_encoding_from_meta(content)
        if encoding:
            return encoding, 0.95
        
        # 3. 使用 chardet 自动检测编码
        if content:
            detected = chardet.detect(content)
            if detected and detected.get('encoding'):
                encoding = detected['encoding']
                confidence = detected.get('confidence', 0.0)
                return encoding, confidence
        
        # 4. 默认使用 utf-8
        return 'utf-8', 0.0
    
    @staticmethod
    def _extract_encoding_from_headers(headers: dict) -> Optional[str]:
        """从响应头中提取编码"""
        if not headers:
            return None
        
        # 尝试从 Content-Type 头获取
        content_type = None
        for key in headers:
            if key.lower() == 'content-type':
                value = headers[key]
                # 处理可能是列表的情况
                if isinstance(value, list):
                    content_type = value[0] if value else None
                else:
                    content_type = value
                break
        
        if not content_type:
            return None
        
        # 确保 content_type 是字符串
        if isinstance(content_type, bytes):
            content_type = content_type.decode('utf-8', errors='ignore')
        
        # 解析 charset 参数
        match = re.search(r'charset\s*=\s*([^\s;]+)', content_type, re.IGNORECASE)
        if match:
            charset = match.group(1).strip('\'"')
            return EncodingHandler._normalize_encoding(charset)
        
        return None
    
    @staticmethod
    def _extract_encoding_from_meta(content: bytes) -> Optional[str]:
        """从 HTML meta 标签中提取编码"""
        try:
            # 只检查前 2KB 内容，加快速度
            head_content = content[:2048]
            
            # 尝试使用 utf-8 解码元数据部分
            try:
                head_str = head_content.decode('utf-8', errors='ignore')
            except:
                head_str = head_content.decode('latin-1', errors='ignore')
            
            # 匹配 meta charset 标签
            patterns = [
                r'<meta\s+charset\s*=\s*["\']?([^\s"\'>;]+)',
                r'<meta\s+http-equiv\s*=\s*["\']?content-type["\']?\s+content\s*=\s*["\']?([^"\'>;]*charset=([^\s"\'>;]+))',
                r'charset\s*=\s*([^\s"\'>;]+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, head_str, re.IGNORECASE)
                if match:
                    # 从最后一个捕获组获取编码
                    charset = match.group(1) if match.lastindex == 1 else match.group(match.lastindex)
                    if charset:
                        return EncodingHandler._normalize_encoding(charset)
        except Exception:
            pass
        
        return None
    
    @staticmethod
    def _normalize_encoding(encoding: str) -> Optional[str]:
        """规范化编码名称"""
        if not encoding:
            return None
        
        encoding = encoding.lower().strip()
        
        # 使用别名映射
        if encoding in EncodingHandler.ENCODING_ALIASES:
            return EncodingHandler.ENCODING_ALIASES[encoding]
        
        # 验证编码是否有效
        try:
            ''.encode(encoding)
            return encoding
        except LookupError:
            return None
    
    @staticmethod
    def decode_content(content: bytes, headers: dict = None, fallback_encoding: str = 'utf-8') -> str:
        """
        智能解码响应内容
        
        Args:
            content: 二进制内容
            headers: 响应头（可选）
            fallback_encoding: 失败时的回退编码
        
        Returns:
            解码后的字符串
        """
        if not content:
            return ''
        
        if isinstance(content, str):
            return content
        
        # 自动检测编码
        encoding, confidence = EncodingHandler.detect_encoding(content, headers)
        
        # 尝试用检测到的编码解码
        try:
            return content.decode(encoding, errors='replace')
        except (UnicodeDecodeError, LookupError):
            pass
        
        # 尝试常见编码列表
        common_encodings = ['utf-8', 'gbk', 'gb2312', 'big5', 'iso-8859-1', 'cp936']
        for enc in common_encodings:
            try:
                return content.decode(enc, errors='replace')
            except (UnicodeDecodeError, LookupError):
                continue
        
        # 最后使用回退编码
        return content.decode(fallback_encoding, errors='replace')
    
    @staticmethod
    def get_encoding_info(content: bytes, headers: dict = None) -> dict:
        """
        获取详细的编码信息
        
        Returns:
            {
                'encoding': '检测到的编码',
                'confidence': 置信度,
                'source': '编码来源',
                'methods': ['使用的检测方法']
            }
        """
        info = {
            'encoding': 'utf-8',
            'confidence': 0.0,
            'source': 'default',
            'methods': []
        }
        
        # 尝试从头部提取
        if headers:
            enc = EncodingHandler._extract_encoding_from_headers(headers)
            if enc:
                info['encoding'] = enc
                info['confidence'] = 1.0
                info['source'] = 'Content-Type header'
                info['methods'].append('header')
                return info
        
        # 尝试从 meta 标签提取
        enc = EncodingHandler._extract_encoding_from_meta(content)
        if enc:
            info['encoding'] = enc
            info['confidence'] = 0.95
            info['source'] = 'HTML meta tag'
            info['methods'].append('meta')
            return info
        
        # 使用 chardet 检测
        if content:
            detected = chardet.detect(content)
            if detected and detected.get('encoding'):
                info['encoding'] = detected['encoding']
                info['confidence'] = detected.get('confidence', 0.0)
                info['source'] = 'chardet detection'
                info['methods'].append('chardet')
        
        return info
