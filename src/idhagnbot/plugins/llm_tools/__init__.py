from pydantic import BaseModel, Field

from idhagnbot.config import ConfigWrapper


class Config(BaseModel):
    masters: set[str] = Field(default_factory=set)
    use_superusers_as_masters: bool = True
    master_prompt: str = ""
    others_prompt: str = ""


CONFIG = ConfigWrapper(Config)

from . import llm_block as llm_block
from . import master_prompt as master_prompt
from . import onebot_forward as onebot_forward
