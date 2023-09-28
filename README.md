# matridge

[Home](https://sr.ht/~nicoco/slidge) |
[Docs](https://slidge.im/matridge) |
[Issues](https://todo.sr.ht/~nicoco/matridge) |
[Patches](https://lists.sr.ht/~nicoco/public-inbox) |
[Chat](xmpp:slidge@conference.nicoco.fr?join)

A
[feature-rich](https://slidge.im/matridge/features.html)
[Matrix](https://matrix.org) to
[XMPP](https://xmpp.org/) puppeteering
[gateway](https://xmpp.org/extensions/xep-0100.html), based on
[slidge](https://slidge.im) and
[nio](https://matrix-nio.readthedocs.io/).

[![builds.sr.ht status](https://builds.sr.ht/~nicoco/matridge/commits/master/ci.yml.svg)](https://builds.sr.ht/~nicoco/matridge/commits/master/ci.yml)
[![containers status](https://builds.sr.ht/~nicoco/matridge/commits/master/container.yml.svg)](https://builds.sr.ht/~nicoco/matridge/commits/master/container.yml)
[![pypi status](https://badge.fury.io/py/matridge.svg)](https://pypi.org/project/matridge/)

## Installation

Refer to the [slidge admin documentation](https://slidge.im/core/admin/)
for general info on how to set up an XMPP server component.

### Containers

From [dockerhub](https://hub.docker.com/r/nicocool84/matridge)

```sh
docker run docker.io/nicocool84/matridge
```

### Python package

With [pipx](https://pypa.github.io/pipx/):

```sh

# for the latest stable release (if any)
pipx install matridge

# for the bleeding edge
pipx install matridge \
    --pip-args='--extra-index-url https://slidge.im/repo'

matridge --help
```

## Dev

```sh
git clone https://git.sr.ht/~nicoco/matridge
cd matridge
docker-compose up
```
