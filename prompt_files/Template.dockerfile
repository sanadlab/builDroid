FROM ubuntu:22.04

LABEL Description="This image provides a base Android development environment."

ENV DEBIAN_FRONTEND=noninteractive

# set default build arguments
ARG SDK_VERSION=commandlinetools-linux-11076708_latest.zip
ARG ANDROID_BUILD_VERSION=35
ARG ANDROID_TOOLS_VERSION=35.0.0

ENV ADB_INSTALL_TIMEOUT=10
ENV ANDROID_HOME=/home/vscode/Android/Sdk
ENV ANDROID_SDK_ROOT=${ANDROID_HOME}

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH=${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/emulator:${ANDROID_HOME}/platform-tools:${ANDROID_HOME}/tools:${ANDROID_HOME}/tools/bin:${PATH}

# Install system dependencies
RUN apt update -qq && apt install -qq -y --no-install-recommends \
    apt-transport-https \
    curl \
    file \
    git \
    git-lfs \
    libc++1-11 \
    libgl1 \
    make \
    openjdk-17-jdk-headless \
    patch \
    rsync \
    unzip \
    sudo \
    ninja-build \
    zip \
    && rm -rf /var/lib/apt/lists/*

# Download and install Android SDK command-line tools
RUN curl -sS https://dl.google.com/android/repository/${SDK_VERSION} -o /tmp/sdk.zip \
    && mkdir -p ${ANDROID_HOME}/cmdline-tools \
    && unzip -q -d ${ANDROID_HOME}/cmdline-tools /tmp/sdk.zip \
    && mv ${ANDROID_HOME}/cmdline-tools/cmdline-tools ${ANDROID_HOME}/cmdline-tools/latest \
    && rm /tmp/sdk.zip \
    && yes | sdkmanager --licenses \
    && yes | sdkmanager "platform-tools" \
    "platforms;android-$ANDROID_BUILD_VERSION" \
    "build-tools;$ANDROID_TOOLS_VERSION" \
    && rm -rf ${ANDROID_HOME}/.android \
    && chmod 777 -R ${ANDROID_HOME}

# Copy project files
COPY . .