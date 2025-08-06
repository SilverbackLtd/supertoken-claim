import click
from ape.cli import (ConnectedProviderCommand, account_option, ape_cli_context,
                     network_option)
from ape_safe._cli.click_ext import safe_argument


@click.command(cls=ConnectedProviderCommand)
@ape_cli_context()
@network_option()
@account_option()
@safe_argument
@click.argument("token")
@click.option("--receiver", default=None)
@click.option("--gas-limit", type=int, default=None)
@click.option("--publish", default=False, is_flag=True)
def cli(cli_ctx, safe, token, receiver, gas_limit, publish, account):
    cli_ctx.local_project.ClaimModule.deploy(
        safe,
        token,
        receiver or account,
        sender=account,
        gas_limit=gas_limit,
        publish=publish,
    )
