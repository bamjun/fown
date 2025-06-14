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

### 로컬 테스트
```
PYTHONPATH=src python src\\fown\\cli\\main.py --help
```