import os
from decimal import Decimal

from ape import Contract, accounts
from ape_safe import SafeAccount
from ape_tokens import tokens
from silverback import SilverbackBot

bot = SilverbackBot()
assert bot.signer, "A signer is needed to run this bot"

grant = Contract(os.environ["SUPERFLUID_GRANT_ADDRESS"])
if not (grantee := os.environ.get("GRANTEE_SAFE_ALIAS")):
    grantee = bot.signer

# NOTE: If claiming for a Safe, set `GRANTEE_ADDRESS_OR_ALIAS=<safe.alias>`
else:
    grantee = accounts.load(grantee)
    assert isinstance(grantee, SafeAccount), (
        "Grantee must be Safe if different than signer"
    )
    assert (
        bot.signer in grantee.local_signers or bot.signer in grantee.all_delegates()
    ), "Signer must either be a signer in Safe, or a delegate"

TOKEN = tokens[os.environ["GRANT_TOKEN_SYMBOL"]]
CLAIM_THRESHOLD = Decimal(os.environ["GRANT_CLAIM_THRESHOLD"])
RECEIVER = os.environ.get("GRANT_CLAIM_RECEIVER")


@bot.on_startup()
def setup(_):
    bot.state.claim_in_progress = False

    if not isinstance(grantee, SafeAccount):
        return  # Claiming for self or unaffiliated account

    # NOTE: If grantee is an AccountAPI class that isn't `bot.signer`,
    #       assume it is a Safe and check if any txns already pending
    for safe_tx, _ in grantee.pending_transactions():
        if safe_tx.to == grant:
            bot.state.claim_in_progress = True
            break


@bot.cron(os.environ.get("GRANT_CHECK_FREQUENCY", "*/5 * * * *"))
def available(_):
    return Decimal(grant.balanceOf(grantee)) / 10 ** Decimal(TOKEN.decimals())


if isinstance(grantee, SafeAccount):

    @bot.on_metric("available", ge=CLAIM_THRESHOLD)
    async def execute_claim(available: Decimal):
        claim_amount = int(
            (available - (available % CLAIM_THRESHOLD)) * 10 ** TOKEN.decimals()
        )

        nonce_to_replace = None
        if bot.state.claim_in_progress:  # Another task is claiming
            for safe_tx, _ in grantee.pending_transactions():
                if safe_tx.to == grant:
                    try:
                        decoded = grant.downgrade.decode(safe_tx.data)[1]
                    except Exception:
                        try:
                            decoded = grant.downgradeTo.decode(safe_tx.data)[1]
                        except Exception:
                            decoded = {}

                    if (amount := decoded.get("amount")) == claim_amount:
                        return  # Transaction already exists

                    elif amount < claim_amount:
                        nonce_to_replace = safe_tx.nonce
                        break

        bot.state.claim_in_progress = True
        if RECEIVER:
            txn = grant.downgradeTo.as_transaction(
                RECEIVER,
                claim_amount,
                sender=grantee,
                # NOTE: Gas limit doesn't matter, but bypasses gas estimation error
                gas_limit=200_000,
                nonce=nonce_to_replace,  # if `None`, proposed as new SafeTx
            )
        else:
            txn = grant.downgrade.as_transaction(
                claim_amount,
                sender=grantee,
                # NOTE: Gas limit doesn't matter, but bypasses gas estimation error
                gas_limit=200_000,
                nonce=nonce_to_replace,  # if `None`, proposed as new SafeTx
            )
        grantee.propose(txn, submitter=bot.signer)
        # NOTE: SafeTx submitted but not broadcast yet

else:  # bot.signer == grantee

    @bot.on_metric("available", ge=CLAIM_THRESHOLD)
    async def execute_claim(available: Decimal):
        claim_amount = int(
            (available - (available % CLAIM_THRESHOLD)) * 10 ** TOKEN.decimals()
        )
        if not bot.state.claim_in_progress:
            bot.state.claim_in_progress = True
            if RECEIVER:
                grant.downgradeTo(
                    RECEIVER, claim_amount, sender=bot.signer, confirmations_required=0
                )

            else:
                grant.downgrade(
                    claim_amount, sender=bot.signer, confirmations_required=0
                )
            # We have successfully claimed if transaction broadcasts


# Record when the claim is completed.
@bot.on_(grant.TokenDowngraded, account=grantee)
def claimed(log):
    bot.state.claim_in_progress = False
    return log.amount
