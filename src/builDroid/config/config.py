"""Configuration class to store the state of bools for different scripts access."""
from __future__ import annotations

import os

from pathlib import Path
from typing import Optional

class Config():
    name: str = "Config"
    description: str = "Description"
    ########################
    # Application Settings #
    ########################
    debug_mode: bool = False
    plain_output: bool = False

    ##########################
    # Agent Control Settings #
    ##########################
    # Paths
    wokring_directory: Path = None
    workspace_path: Optional[Path] = None
    # Model configuration
    llm_model: str = None
    temperature: float = 1.0
    openai_functions: bool = False
    cycle_limit: int = 0
    conversation: bool = False

    ###############
    # Credentials #
    ###############
    # OpenAI
    openai_api_key: Optional[str] = ""
    openai_api_base: Optional[str] = ""
    
def set_api_token(config: Config) -> None:
    """Setup api tokens for agent."""
    config.openai_api_key = os.getenv("API_KEY", default="")
    config.openai_api_base = os.getenv("BASE_URL", default="")
    config.llm_model = os.getenv("LLM_MODEL", default="")