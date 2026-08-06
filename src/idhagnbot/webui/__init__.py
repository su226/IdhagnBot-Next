from fastapi import Depends, Response
from pydantic import BaseModel

from idhagnbot.webui.common import APP, ResponseData, authorize
from idhagnbot.webui.config import setup as setup_config
from idhagnbot.webui.dashboard import setup as setup_dashboard


class AuthorizeResponseData(BaseModel):
    modules: set[str]


@APP.post("/authorize", dependencies=[Depends(authorize)])
async def handle_authorize() -> Response:
    return ResponseData.res_success(
        AuthorizeResponseData(
            modules={"dashboard", "config"},
        ),
    )


setup_dashboard(APP)
setup_config(APP)
