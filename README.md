# Mondoo

Mondoo is a knowledge engine designed to orchestrate multimodal data sources, including text, images, audio, and video.


> [NOTE]
> This project is under intensive development. Please take care when deploying it in production environments.
>
> If you have any interest, ideas, or motivation, please contact me at zhanbo.fang@alumnos.upm.es.

## Highlight Features



## Dependencies Installation

Install all dependencies except from pytorch and PaddlePaddle-GPU:

```
# if you use uv
uv sync # in default way
uv venv .venv

# otherwise,
pip install -r base-requirements.txt
```

Note: it's necessary to execute the pytorch installation instruction at first, then execute installing paddlepaddle-gpu. That's because they depend on some common wheels in different versions, which cause conflicts.
Since paddlepaddle-gpu is stricter in term of such dependencies, you should install it after pytorch isntallation 
so that its dependencies installation can overrwrite the previous one.


Download pytorch-2.11 + cuda-13.0

```
uv pip install torch==2.11.0 torchvision==0.26.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu130
```

Download PaddlePaddle-GPU

```
uv pip install paddlepaddle-gpu==3.2.1 -i https://www.paddlepaddle.org.cn/packages/stable/cu130/
```