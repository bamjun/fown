
# fown

GitHub CLI를 활용하여 GitHub 레이블과 프로젝트를 자동화하는 작은 Python CLI 도구입니다.

## 목차
- [설치 방법](#설치-방법)
- [기능](#기능)
- [사용 방법](#사용-방법)
  - [아카이브 레포지토리 생성](#아카이브-레포지토리-생성)
  - [레이블 동기화](#레이블-동기화)
  - [스크립트 관리](#스크립트-관리)
- [요구사항](#요구사항)
- [문서](#문서)
- [라이선스](#라이선스)

## 설치 방법

### uv를 통한 설치
```bash
# 모든 레이블 삭제
uvx fown labels clear-all

# 기본 레이블 추가
uvx fown labels apply
```

### pip을 통한 설치
```bash
pip install fown
```

## 기능

- GitHub 레이블 생성, 업데이트, 동기화
- GitHub 프로젝트 자동 관리
- 설정 파일을 통한 일괄 작업
- 빠르고 간단한 설정
- GitHub CLI (`gh`) 기반 동작

## 사용 방법

### 아카이브 레포지토리 생성
```bash
# 기본: private 레포지토리 생성
fown make-fown-archive

# public 레포지토리 생성
fown make-fown-archive --public
```

### 레이블 동기화
```bash
# 기본 레이블로 동기화
fown labels sync

# 아카이브 레포지토리에서 동기화
fown labels sync --archive
```

### 스크립트 관리
```bash
# 스크립트 실행
fown script use

# 스크립트 추가 (.sh 파일만 지원)
fown script add <script-file.sh>

# 스크립트 삭제
fown script delete
```

## 요구사항

- Python 3.8 이상
- GitHub CLI (`gh`) 설치 및 인증 필요

GitHub CLI 설치 방법:  
https://cli.github.com/

## 문서

- [테스트 서버 PyPI](https://test.pypi.org/project/fown/)
- [메인 서버 PyPI](https://pypi.org/project/fown/)
- [GitHub](https://github.com/bamjun/fown)

## 라이선스

MIT License
