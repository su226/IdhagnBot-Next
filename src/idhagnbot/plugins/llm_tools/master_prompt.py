from arclet.entari.config import EntariConfig
from arclet.letoderea import on
from entari_plugin_llm import LLMCollectVariableEvent

from idhagnbot.plugins.llm_tools import CONFIG


def is_master(platform: str, user_id: str) -> bool:
    if (
        CONFIG.current.use_superusers_as_masters
        and user_id in EntariConfig.instance.basic.superusers.get(platform, [])
    ):
        return True
    return f"{platform}:{user_id}" in CONFIG.current.masters


@on(LLMCollectVariableEvent, priority=0)
async def add_master_prompt(event: LLMCollectVariableEvent) -> None:
    user = event.session.event.user
    if not user:
        return
    if is_master(event.session.account.platform, user.id):
        if CONFIG.current.master_prompt:
            event.instructions.append(CONFIG.current.master_prompt)
    elif CONFIG.current.others_prompt:
        event.instructions.append(CONFIG.current.others_prompt)
