"""
环境变量加载工具：从 .env 文件加载配置
"""
import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def load_env_file(env_path: Optional[str] = None) -> bool:
    """
    加载 .env 文件
    
    Args:
        env_path: .env 文件路径，如果为 None，则自动查找项目根目录下的 .env 文件
    
    Returns:
        bool: 是否成功加载 .env 文件
    """
    if load_dotenv is None:
        return False
    
    if env_path is None:
        # 自动查找项目根目录下的 .env 文件
        # 从当前文件位置向上查找，找到包含 scrapy.cfg 的目录作为项目根目录
        current_file = Path(__file__).resolve()
        
        # 从当前文件位置向上查找 scrapy.cfg
        project_root = current_file.parent.parent.parent  # crawler/utils -> crawler -> project_root
        env_path = project_root / ".env"
        
        # 如果当前目录没有 scrapy.cfg，向上查找
        if not (project_root / "scrapy.cfg").exists():
            for parent in current_file.parents:
                if (parent / "scrapy.cfg").exists():
                    env_path = parent / ".env"
                    break
    
    env_file = Path(env_path) if isinstance(env_path, str) else env_path
    
    if env_file.exists():
        result = load_dotenv(env_file, override=False)  # override=False 表示环境变量优先
        if result:
            # 调试模式：可以通过环境变量启用
            if os.getenv("DEBUG_ENV_LOAD", "").lower() in ("1", "true", "yes"):
                print(f"[env_loader] 已加载 .env 文件: {env_file}")
        return result
    else:
        # 调试模式：显示未找到 .env 文件
        if os.getenv("DEBUG_ENV_LOAD", "").lower() in ("1", "true", "yes"):
            print(f"[env_loader] 未找到 .env 文件: {env_file}")
    
    return False


# 在模块导入时自动加载 .env 文件
load_env_file()

