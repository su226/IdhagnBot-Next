from arclet import letoderea
from arclet.entari import metadata, plugin_config
from arclet.entari.event.base import SatoriEvent
from arclet.entari.filter.parse import parse_filter
from arclet.letoderea import BLOCK, ExitState, bypass_if
from pydantic import BaseModel


class Config(BaseModel):
    filter_before_record: str = "True"
    filter_after_record: str = "True"


metadata("", config=Config)
CONFIG = plugin_config(Config)
filter_before_record = parse_filter(CONFIG.filter_before_record)
filter_after_record = parse_filter(CONFIG.filter_after_record)


@letoderea.on(SatoriEvent, priority=-1000)
@bypass_if(filter_before_record)
async def apply_filter_before_record() -> ExitState:
    return BLOCK


@letoderea.on(SatoriEvent, priority=-900)
@bypass_if(filter_after_record)
async def apply_filter_after_record() -> ExitState:
    return BLOCK
