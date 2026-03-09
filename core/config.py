"""
配置管理模块
负责加载 .env 文件和管理全局配置项。
"""

import os
from pathlib import Path
from dotenv import load_dotenv


# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 加载 .env 文件
load_dotenv(PROJECT_ROOT / ".env")


class Config:
    """全局配置类，从环境变量中读取配置。"""

    # --- LLM 相关 ---
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.7"))
    MAX_COMPLETION_TOKENS: int = int(os.getenv("MAX_COMPLETION_TOKENS", "4096"))  # 单轮最大输出 token 数，防止思考被截断

    # --- Agent 相关 ---
    MAX_REACT_STEPS: int = int(os.getenv("MAX_REACT_STEPS", "10"))
    # 观察结果在界面展示时的最大字符数，0 表示不截断
    OBSERVATION_DISPLAY_MAX_LENGTH: int = int(os.getenv("OBSERVATION_DISPLAY_MAX_LENGTH", "2000"))

    # --- 路径相关 ---
    SKILLS_DIR: Path = PROJECT_ROOT / "skills"
    WORKSPACE_DIR: Path = PROJECT_ROOT / os.getenv("WORKSPACE_DIR", "workspace")
    # Agent 自我升级时保存新技能的目录（skills/user/），与内置技能隔离
    USER_SKILLS_DIR: Path = SKILLS_DIR / "user"

    @classmethod
    def validate(cls) -> list[str]:
        """校验配置，返回错误信息列表（空列表表示配置合法）。"""
        errors: list[str] = []
        if not cls.OPENAI_API_KEY or cls.OPENAI_API_KEY.startswith("sk-your"):
            errors.append("请在 .env 文件中设置有效的 OPENAI_API_KEY")
        if cls.MAX_REACT_STEPS < 1:
            errors.append("MAX_REACT_STEPS 必须 >= 1")
        return errors

    @classmethod
    def summary(cls) -> str:
        """返回当前配置摘要（隐藏密钥）。"""
        masked_key = cls.OPENAI_API_KEY[:8] + "..." if len(cls.OPENAI_API_KEY) > 8 else "未设置"
        return (
            f"模型: {cls.OPENAI_MODEL}\n"
            f"API Base: {cls.OPENAI_BASE_URL}\n"
            f"API Key: {masked_key}\n"
            f"温度: {cls.TEMPERATURE}\n"
            f"最大输出长度: {cls.MAX_COMPLETION_TOKENS} tokens\n"
            f"最大推理步数: {cls.MAX_REACT_STEPS}\n"
            f"观察展示长度: {cls.OBSERVATION_DISPLAY_MAX_LENGTH} 字符（0=不截断）\n"
            f"技能目录: {cls.SKILLS_DIR}\n"
            f"用户技能目录: {cls.USER_SKILLS_DIR}\n"
            f"工作区: {cls.WORKSPACE_DIR}"
        )
