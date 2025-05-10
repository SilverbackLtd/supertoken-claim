# Overview

Bot for automating claims through Superfluid Vesting

## Installation

You can run this bot by downloading this repo and [installing Silverback](https://docs.apeworx.io/silverback/stable/userguides/quickstart.html#installation), or run it using `docker`:

```sh
docker run ghcr.io/silverbackltd/supertoken-claim-bot:latest run --network <ecosystem>:<network> --account <alias>
```

```{warning}
Running with Docker requires having a configured wallet inside the docker container context.
It is recommended to use this image as a base image, and install your own.
See [here](https://docs.apeworx.io/ape/latest/userguides/accounts.html#automation) for more information.
```

## Usage

To run this bot, simple install it

Required:

- `SUPERFLUID_GRANT_ADDRESS`: Address of grant vesting Supertoken
- `GRANT_TOKEN_SYMBOL`: The symbol of the token to claim
- `GRANT_CLAIM_THRESHOLD`: The min amount of `GRANT_TOKEN_SYMBOL` to claim at a time

Optional

- `GRANTEE_SAFE_ALIAS`: Specify the alias of a configured Safe multisig contract w/ `ape-safe`

```{notice}
Using `GRANTEE_SAFE_ALIAS` will only submit the transaction to the SafeAPI, unless all of your signers are loaded locally.
```

```{warning}
If using `GRANTEE_SAFE_ALIAS`, then `bot.signer` (the value of `--account <alias>`) **must** either be a signer or a approved submitter to the Safe API.
```
