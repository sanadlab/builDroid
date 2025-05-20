#!/bin/bash

# Install dependencies required for building Python
apt-get update && apt-get install -y \
    build-essential \
    zlib1g-dev \
    libncurses5-dev \
    libgdbm-dev \
    libnss3-dev \
    libssl-dev \
    libreadline-dev \
    libffi-dev \
    curl \
    wget \
    libbz2-dev \
    git-lfs

# Download Python 3.10.x source code from the official website
PYTHON_VERSION="3.10.10"
wget https://www.python.org/ftp/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tgz

# Extract the tarball
tar -xvzf Python-$PYTHON_VERSION.tgz
cd Python-$PYTHON_VERSION

# Configure and install Python
./configure --enable-optimizations
make -j"$(nproc)"  # Use all available CPU cores for faster compilation
make altinstall  # altinstall to avoid overwriting default python

# Set Python 3.10 as the default python3
update-alternatives --install /usr/bin/python3 python3 /usr/local/bin/python3.10 1
update-alternatives --config python3

# Install pip for Python 3.10
#curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
#python3.10 get-pip.py

# Clean up
rm -rf /Python-$PYTHON_VERSION
rm Python-$PYTHON_VERSION.tgz
#rm get-pip.py

# Check if Python 3.10 is installed correctly
python3 --version