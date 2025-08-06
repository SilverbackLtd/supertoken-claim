interface ISafeModuleManager:
    def execTransactionFromModule(
        to: address,
        amount: uint256,
        data: Bytes[65535],
        operation: uint8,
    ) -> bool: nonpayable


SAFE: immutable(ISafeModuleManager)
SUPERTOKEN: immutable(address)
RECEIVER: immutable(address)


@deploy
def __init__(
    safe: ISafeModuleManager,
    supertoken: address,
    receiver: address,
):
    SAFE = safe
    SUPERTOKEN = supertoken
    RECEIVER = receiver


@external
def claim(amount: uint256):
    # TODO: After using Safe module for swaps, refactor this to just `downgrade`
    assert extcall SAFE.execTransactionFromModule(
        SUPERTOKEN,
        0,  # No ether
        abi_encode(RECEIVER, amount, method_id=method_id("downgradeTo(address,uint256)")),
        0,  # Normal call
    )
