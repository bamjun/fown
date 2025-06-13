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


## 로컬 개발 실행명렁어  
- 가상환경 진입  

  ```  
    poetry shell
  ```  

- 실행  

  ```
    PYTHONPATH=src python src\\fown\\cli.py
  ```