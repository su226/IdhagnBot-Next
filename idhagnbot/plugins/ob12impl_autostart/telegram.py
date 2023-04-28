def start(
  api_id: int,
  api_hash: str,
  bot_token: str,
  proxy: str,
  port: int,
  log_level: str,
) -> None:
  import asyncio

  from idhagnbot.ob12impl.telegram import App
  from idhagnbot.obc.v12.driver.wsrev import WebSocketRevDriver
  from idhagnbot.plugins.ob12impl_autostart.common import config_logger, logger, wait_shutdown

  async def main() -> None:
    config_logger("telegram", log_level)
    app = App(api_id, api_hash, bot_token, proxy)
    ws = WebSocketRevDriver(app, f"127.0.0.1:{port}/onebot/v12/")
    async with app:
      async with ws:
        app.heartbeat = 5000
        logger.success(f"OneBot impl for Telegram bot {app.id} started.")
        await wait_shutdown()
        logger.info(f"Shutting down OneBot impl for Telegram bot {app.id}.")

  asyncio.run(main())
