# install dependencies
FROM docker.io/nicocool84/slidge-builder AS builder

COPY poetry.lock pyproject.toml /build/
RUN poetry export --without-hashes >requirements.txt
RUN python3 -m pip install --requirement requirements.txt

# main container
FROM docker.io/nicocool84/slidge-base AS Matridge
COPY --from=builder /venv /venv
COPY ./matridge /venv/lib/python/site-packages/legacy_module

# dev container
FROM docker.io/nicocool84/slidge-dev AS dev

COPY --from=builder /venv /venv
