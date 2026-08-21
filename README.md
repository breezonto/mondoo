# Mondoo

Mondoo is a knowledge engine designed to store, transform, and orchestrate multimodal data sources—including text, images, audio, and video—from offline files and crawled web data. It aims to provide structured world knowledge to Generative AI systems, supporting applications ranging from text-to-text generation with LLMs to text-to-image generation with diffusion models.

The project was initially inspired by the _Data Infrastructure_ section of the [z-image's technical report](https://arxiv.org/abs/2511.22699), which highlighted the importance of large-scale, high-quality data infrastructure for generative AI. Mondoo explores this idea from a broader knowledge-engineering perspective, with an emphasis on building an infrastructure that can ingest, organize, transform, and orchestrate heterogeneous data as reusable knowledge for generative AI.

Mondoo is currently a research-oriented project and may eventually evolve into the foundation of my PhD research. Stay tuned. 🚀


> [NOTE]
> This project is under intensive development. Please take care when deploying it in production environments.
>
> If you have any interest, ideas, or motivation, please contact me at zhanbo.fang@alumnos.upm.es.

## Highlights

## Installation 

For detail dependencies installation guide, please refers to [installation guide](./docs/installation-guide.md). In general, Mondoo has below dependencies in system-wide:

- **Python 3.12** (other versions may works, but not guaranteed); 

- **PostgreSQL**, for persistent data storage;
    
- **Redis**, for caching and as data structure server;

- **CUDA 13.0**, optionally, if you need some features like _local deployment of base model_ and _Optical Character Recognition_ (OCR)  


### Package Installation (from Source)

For package installation from source, we use uv to manage and build it. If you haven't clone it yet:

```
git clone https://github.com/breezonto/mondoo.git
```

Inside the root directory of cloned repo, create the virtual environment:

```
uv venv .venv 
```

To Install the package dependencies, there are three group options:

- **standard**: the standard version of Mondoo, including some fundamental features as retrieval system

- **ontology**: powering Mondoo with ontology and semantic web, the core exploring direction in research (recommended) 

- **gpu**: enable some GPU-capable features

```
# if you only pick up standard version
uv sync --group standard

# or if you only wanna try ontology
uv sync --group ontology

# also, you can freely pick options in combination way (it's also applicable to all group options)
uv sync --group standard --group ontoloy
```

## Launch Services

Please refer to [estar-instructions](estar-instructions.md)


## Mondoo Frontend

Comming soon...