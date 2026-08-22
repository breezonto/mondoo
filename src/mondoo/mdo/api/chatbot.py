from pathlib import Path


path = Path('mdo/literate/role/default.md')
if path.exists():
    with open(path, 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT_DEFAULT = f.read()
else:
    SYSTEM_PROMPT_DEFAULT = "You are an helpful assistant"