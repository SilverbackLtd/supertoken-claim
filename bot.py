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

    elif bot.state.claim_in_progress:  # Another task is claiming
        return dict(available=available / 10 ** TOKEN.decimals())

    claiming = bot.state.claim_in_progress = True

    if isinstance(grantee, SafeAccount):
        txn = grant.downgrade.as_transaction(CLAIM_THRESHOLD, sender=grantee)
        grantee.propose(txn, submitter=bot.signer)
        # NOTE: SafeTx submitted but not broadcast yet

    else:  # grantee == bot.signer
        grant.downgrade(CLAIM_THRESHOLD, sender=bot.signer, confirmations_required=0)
        # We have successfully claimed if transaction broadcasts
        available -= CLAIM_THRESHOLD
        claiming = False

    return dict(available=available / 10 ** TOKEN.decimals(), claiming=claiming)


# Record when the claim is completed.
@bot.on_(grant.TokenDowngraded, account=grantee)
def receive_claim(log):
    bot.state.claim_in_progress = False
    return dict(claimed=log.amount / 10 ** TOKEN.decimals(), claiming=False)
