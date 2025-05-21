import os

from ape import Contract, accounts, convert
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
CLAIM_THRESHOLD = convert(
    f"{os.environ['GRANT_CLAIM_THRESHOLD']} {TOKEN.symbol()}", int
)


@bot.on_startup()
def setup(_):
    bot.state.claim_in_progress = False

    if not isinstance(grantee, SafeAccount):
        return dict(claiming=False)  # Claiming for self or unaffiliated account

    # NOTE: If grantee is an AccountAPI class that isn't `bot.signer`,
    #       assume it is a Safe and check if any txns already pending
    for safe_tx, _ in grantee.pending_transactions():
        if safe_tx.to == grant:
            bot.state.claim_in_progress = True

    return dict(claiming=bot.state.claim_in_progress)


@bot.cron(os.environ.get("GRANT_CLAIM_FREQUENCY", "*/5 * * * *"))
def check_grant(_):
    if (
        available := grant.balanceOf(grantee)
    ) < CLAIM_THRESHOLD:  # Not enough yet to claim
        return dict(available=available / 10 ** TOKEN.decimals())

    amount_to_claim = available - (available % CLAIM_THRESHOLD)

    nonce_to_replace = None
    if bot.state.claim_in_progress:  # Another task is claiming
        for safe_tx, _ in grantee.pending_transactions():
            if safe_tx.to == grant:
                try:
                    decoded = grant.downgrade.decode(safe_tx.data)[1]
                except Exception:
                    decoded = {}

                if decoded.get("amount") < amount_to_claim:
                    nonce_to_replace = safe_tx.nonce
                    break

        else:
            # Claim in progress, and it is the correct amount
            return dict(available=available / 10 ** TOKEN.decimals())

    claiming = bot.state.claim_in_progress = True
    if isinstance(grantee, SafeAccount):
        txn = grant.downgrade.as_transaction(
            amount_to_claim,
            sender=grantee,
            # NOTE: Gas limit doesn't matter, but bypasses gas estimation error
            gas_limit=200_000,
            nonce=nonce_to_replace,
        )
        grantee.propose(txn, submitter=bot.signer)
        # NOTE: SafeTx submitted but not broadcast yet

    else:  # grantee == bot.signer
        grant.downgrade(amount_to_claim, sender=bot.signer, confirmations_required=0)
        # We have successfully claimed if transaction broadcasts
        available -= amount_to_claim
        claiming = False

    return dict(available=available / 10 ** TOKEN.decimals(), claiming=claiming)


# Record when the claim is completed.
@bot.on_(grant.TokenDowngraded, account=grantee)
def receive_claim(log):
    bot.state.claim_in_progress = False
    return dict(claimed=log.amount / 10 ** TOKEN.decimals(), claiming=False)
