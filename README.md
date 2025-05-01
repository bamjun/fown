
# fown

Tiny Python CLI to automate GitHub labels and projects using the GitHub CLI.

## Features

- Create, update, and sync GitHub labels easily
- Manage GitHub projects automatically
- Batch operations via simple config files
- Fast and minimal setup
- Powered by GitHub CLI (`gh`)

## Quick Start

### via uv

- clear all labels in repo issue 
```
uvx fown labels clear-all
```

- add default labels in repo issue
```
uvx fown labels apply
```


### via pip

```bash
pip install fown
```

```bash
# Apply labels from a file
fown labels apply --repo-url https://github.com/your-username/your-repo --file labels.yaml

# Sync project settings
fown projects sync --repo-url https://github.com/your-username/your-repo --config project_config.yaml

# clear all labels
fown labels clear-all
```

## Requirements

- Python 3.8+
- GitHub CLI (`gh`) installed and authenticated

Install GitHub CLI:  
https://cli.github.com/

## Usage

You can use `fown` commands to:

- Batch create/update labels
- Manage multiple repositories at once
- Sync project settings from templates

More usage examples are coming soon!

## Docs

[Pypi for TestServer](https://test.pypi.org/project/fown/)  
[Pypi for MainServer](https://pypi.org/project/fown/)  
[Github](https://github.com/bamjun/fown)  

## License

MIT License
