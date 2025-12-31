"""
时区处理工具模块
支持本地时区时间获取和转换
"""
from datetime import datetime, timezone, timedelta
import os


class TimezoneHelper:
    """时区处理助手类"""
    
    # 默认时区为 +08:00（中国时间），可通过环境变量 TIMEZONE_OFFSET 配置
    DEFAULT_TIMEZONE_OFFSET = int(os.getenv("TIMEZONE_OFFSET", "8"))
    
    @classmethod
    def get_local_timezone(cls) -> timezone:
        """
        获取当前地区的时区对象
        
        Returns:
            timezone 对象
        """
        return timezone(timedelta(hours=cls.DEFAULT_TIMEZONE_OFFSET))
    
    @classmethod
    def get_now(cls, with_tz: bool = True) -> datetime:
        """
        获取当前地区的时间
        
        Args:
            with_tz: 是否包含时区信息（默认 True）
        
        Returns:
            当前时间的 datetime 对象
        """
        utc_time = datetime.now(timezone.utc)
        local_tz = cls.get_local_timezone()
        local_time = utc_time.astimezone(local_tz)
        
        if with_tz:
            return local_time
        else:
            return local_time.replace(tzinfo=None)
    
    @classmethod
    def get_now_isoformat(cls) -> str:
        """
        获取当前地区时间的 ISO 格式字符串
        
        Returns:
            ISO 格式的时间字符串，包含时区信息
        """
        return cls.get_now(with_tz=True).isoformat()
    
    @classmethod
    def get_now_str(cls, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
        """
        获取当前地区时间的格式化字符串
        
        Args:
            fmt: 时间格式字符串（默认 "%Y-%m-%d %H:%M:%S"）
        
        Returns:
            格式化的时间字符串
        """
        return cls.get_now(with_tz=False).strftime(fmt)
