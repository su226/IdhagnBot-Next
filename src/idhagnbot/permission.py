from collections.abc import Awaitable, Callable

from arclet.cithun import Permission
from arclet.cithun.model import ResourceNode, Role, User
from entari_plugin_permission import system  # entair: plugin
from entari_plugin_user import UserSession  # entair: plugin

MEMBER = system.pre_role("idhagnbot.member", "Member")
ADMIN = system.pre_role("idhagnbot.admin", "Administrator")
OWNER = system.pre_role("idhagnbot.owner", "Owner")
GUILD = system.pre_track("idhagnbot.guild", "Guild Admin Track")


@system.on_loaded
async def on_loaded() -> None:
    await system.inherit(ADMIN, MEMBER)
    await system.inherit(OWNER, ADMIN)
    await system.extend_track(
        GUILD,
        [MEMBER, ADMIN, OWNER],
        ["member", "admin", "owner"],
    )


async def permission_strategy(
    user: User,
    resource: ResourceNode,
    context: UserSession | None,
    current_mask: Permission,
    permission_lookup: Callable[
        [User | Role, UserSession | None],
        Awaitable[Permission],
    ],
) -> Permission:
    if context is None or context.session.event.guild is None:
        return current_mask
    if context.session.event.member is None:
        member = await context.session.guild_member_get()
    else:
        member = context.session.event.member
    is_owner = False
    is_admin = False
    for role in member.roles:
        if role.name == "owner":
            is_owner = True
        if role.name == "admin":
            is_admin = True
    if is_owner:
        role = OWNER
    elif is_admin:
        role = ADMIN
    else:
        role = MEMBER
    new_mask = await permission_lookup(role, context)
    return current_mask | new_mask


system.engine.register_strategy(permission_strategy)
