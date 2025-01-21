FROM mcr.microsoft.com/vscode/devcontainers/universal:2.9.0-focal

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update -y && apt-get install -y \
    "bash-completion=$(apt-cache madison bash-completion | awk '{print $3}' | grep '^1:2.10' | head -n 1)" --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create the venv folder and set permissions for anyone to modify---this is necessary to be able to break out the venv folder as a separate docker volume for better performance on Windows hosts
ARG REPO_NAME=copier-base-template
ENV GRAPHQL_LAMBDA_PROJECT_PATH=/workspaces/${REPO_NAME}/graphql_lambda
ENV VENV_PATH=${GRAPHQL_LAMBDA_PROJECT_PATH}/.venv
RUN mkdir -p /workspaces && \
    mkdir -p ${VENV_PATH} && \
    chmod -R 777 /workspaces ${GRAPHQL_LAMBDA_PROJECT_PATH} ${VENV_PATH} && \
    chgrp -R 0 /workspaces ${GRAPHQL_LAMBDA_PROJECT_PATH} ${VENV_PATH}

ENV PNPM_STORE_PATH=/workspaces/${REPO_NAME}/.pnpm-store
RUN mkdir -p /workspaces && \
    mkdir -p ${PNPM_STORE_PATH} && \
    chmod -R 777 /workspaces ${PNPM_STORE_PATH} && \
    chgrp -R 0 /workspaces ${PNPM_STORE_PATH}

ARG APP_NAME=default
ENV APP_PROJECT_PATH=/workspaces/${REPO_NAME}/${APP_NAME}_app
ENV APP_NODE_MODULES_PATH=${APP_PROJECT_PATH}/node_modules
RUN mkdir -p ${APP_NODE_MODULES_PATH} && \
    chmod -R 777 ${APP_PROJECT_PATH} ${APP_NODE_MODULES_PATH} && \
    chgrp -R 0 ${APP_PROJECT_PATH} ${APP_NODE_MODULES_PATH}

# SSH
EXPOSE 2222
