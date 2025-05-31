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
    continuous_limit: int = 0
    chat_stream: bool = False

    ###############
    # Credentials #
    ###############
    # OpenAI
    openai_api_key: Optional[str] = None
    openai_api_base: Optional[str] = None

def get_openai_credentials(self) -> dict[str, str]:
    credentials = {
        "api_key": self.openai_api_key,
        "api_base": self.openai_api_base
    }
    return credentials
    
def set_api_token(config: Config) -> None:
    """Setup api tokens for agent."""
    config.openai_api_key = os.environ.get("api_key")
    config.openai_api_base = os.environ.get("base_url")
    config.llm_model = os.environ.get("llm_model")
