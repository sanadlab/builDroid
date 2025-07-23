FROM ubuntu:22.04

LABEL Description="This image provides a base Android development environment with NDK."

ENV DEBIAN_FRONTEND=noninteractive

# set default build arguments
ARG SDK_VERSION=commandlinetools-linux-11076708_latest.zip
ARG ANDROID_BUILD_VERSION=35
ARG ANDROID_TOOLS_VERSION=35.0.0
ARG NDK_VERSION=26.1.10909125

ENV ADB_INSTALL_TIMEOUT=10
ENV ANDROID_HOME=/home/vscode/Android/Sdk
ENV ANDROID_SDK_ROOT=${ANDROID_HOME}
ENV ANDROID_NDK_HOME=${ANDROID_HOME}/ndk/${NDK_VERSION}

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH=${ANDROID_NDK_HOME}:${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/emulator:${ANDROID_HOME}/platform-tools:${ANDROID_HOME}/tools:${ANDROID_HOME}/tools/bin:${PATH}
RUN echo "export PS1='\\n__AGENT_SHELL_END_MARKER__$ '" >> /root/.bashrc

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
    && rm /tmp/sdk.zip

# Accept licenses
RUN yes | sdkmanager --licenses --sdk_root=${ANDROID_SDK_ROOT}

# Install SDK packages
RUN sdkmanager --install "platform-tools" "platforms;android-$ANDROID_BUILD_VERSION" "build-tools;$ANDROID_TOOLS_VERSION" "ndk;$NDK_VERSION" --sdk_root=${ANDROID_SDK_ROOT}

# Final cleanup and permissions
RUN rm -rf ${ANDROID_HOME}/.android \
    && chmod 777 -R ${ANDROID_HOME}