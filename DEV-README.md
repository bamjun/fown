## 일반서버 배포

```
poetry publish --build

```

```
poetry publish

```

## 테스트서버 배포

```
poetry publish --build -r testpypi

```

### 테스트서버 테스트

```
uv run pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple fown==0.1.4.5
```


### 로컬 테스트
```
PYTHONPATH=src python src\\fown\\cli\\main.py --help
```

