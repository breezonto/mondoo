# Installation Guide

## Compiling Python from Source (if you need)

Ubuntu systems usually come with a default Python interpreter. However, this interpreter is mainly used for system-level tasks such as operating system management and software installation. Therefore, using the system Python interpreter for development is not recommended, because problems such as package pollution may cause system failures. It is recommended to install another Python version manually instead.

Since the official Ubuntu `apt` repositories do not always maintain stable Python versions, it is recommended to compile and install Python from source manually. The following section describes the source compilation, build, and installation process for Python 3.12.13:

Install all dependencies required for building Python:

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  wget \
  curl \
  libssl-dev \
  zlib1g-dev \
  libbz2-dev \
  libreadline-dev \
  libsqlite3-dev \
  libffi-dev \
  libncursesw5-dev \
  libgdbm-dev \
  liblzma-dev \
  tk-dev \
  uuid-dev \
  libxml2-dev \
  libxmlsec1-dev
````

Download the Python source package:

```bash
cd /tmp # You can use any directory, but a temporary directory is recommended
sudo wget https://www.python.org/ftp/python/3.12.2/Python-3.12.2.tgz
sudo tar -xf Python-3.12.2.tgz
cd Python-3.12.2
```

Configure build options for `make`:

```bash
sudo ./configure --enable-optimizations --with-lto
```

Build Python:

```bash
make -j $(nproc)
```

Install the compiled Python and verify the installation (Note: always use `altinstall` instead of `install`, otherwise the default system interpreter under `/usr/bin` may be overwritten):

```bash
sudo make altinstall # Installed under /usr/local by default
python3.12 --version
pip3.12 --version
```

Since the default Ubuntu Python executable is named `python3`, while the manually installed Python executable is named `python3.12`, symbolic links can be created for convenience:

```bash
sudo ln -s /usr/local/bin/python3.12 /usr/local/bin/python
sudo ln -s /usr/local/bin/pip3.12 /usr/local/bin/pip3

# Verify
python --version
pip --version
which python
which pip
```

---

## Database System Installation

The database systems used by this software are mainly PostgreSQL and Redis. PostgreSQL is used for persistent data storage, while Redis is used for data caching:

```bash
sudo apt update

sudo apt install redis-server -y # Install Redis
sudo apt install postgresql postgresql-contrib -y # Install PostgreSQL
```

Enable and test Redis:

```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server
systemctl status redis-server # Check Redis status
redis-cli ping # Expected output: PONG
```

Enable PostgreSQL:

```bash
sudo systemctl enable postgresql
sudo systemctl start postgresql
systemctl status postgresql # Check PostgreSQL status
```

---

## Dependency Installation

First, install `uv`, which is a more modern Python package manager and build tool. Run the following command in the Ubuntu terminal (Note: a proxy may be required to accelerate the download speed):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh # Automatically install uv
uv --version # Verify installation
```

Execute the following commands in the root directory of the project repository to create a Python virtual environment:

```bash
cd mondoo-ai
uv venv .venv
```

**Note:** All subsequent dependency installation operations **must** be performed inside this created Python virtual environment. Otherwise, packages may be installed into the wrong environment, causing missing dependency errors when running the program.

If using VSCode for development (recommended), select the newly created virtual environment from the interpreter selector in the lower-right corner of the interface. If using the command line, activate or exit the virtual environment with:

```bash
# Run from the project root directory
source .venv/bin/activate

# Exit the current virtual environment
deactivate
```

Then install all Python package dependencies except PyTorch and PaddlePaddle:

```bash
uv pip install -r requirements.txt
```

---

## Installing PyTorch and PaddlePaddle

**Note:** PyTorch must be installed before PaddlePaddle. The reason is that their CUDA-related wheel dependencies may conflict. PaddlePaddle-GPU has stricter wheel version requirements, so it should be installed afterwards so that its required dependencies can override the previous ones.

Install PyTorch 2.11 + CUDA 13.0:

```bash
uv pip install torch==2.11.0 torchvision==0.26.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu130
```

Install PaddlePaddle-GPU:

```bash
uv pip install paddlepaddle-gpu==3.2.1 -i https://www.paddlepaddle.org.cn/packages/stable/cu130/
```

---
