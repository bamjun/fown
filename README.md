
# fown

GitHub CLI를 활용하여 GitHub 레이블과 프로젝트를 자동화하는 작은 Python CLI 도구입니다.

## 목차
- [설치 방법](#설치-방법)
- [사용 방법](#사용-방법)
  - [아카이브 레포지토리 생성](#아카이브-레포지토리-생성)
  - [레이블 동기화](#레이블-동기화)
  - [스크립트 관리](#스크립트-관리)
  - [파일 관리](#파일-관리)
- [기능](#기능)
  - [auth](#auth)
  - [file](#file)
  - [make-fown-archive](#make-fown-archive)
- [요구사항](#요구사항)
- [문서](#문서)
- [라이선스](#라이선스)

<h2 id="설치-방법">설치 방법</h2>  

### uvx를 이용한 사용방법
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

<h2 id="사용-방법">사용 방법</h2>

<h3 id="아카이브-레포지토리-생성">아카이브 레포지토리 생성</h3>  

```bash
# 기본: private 레포지토리 생성
fown make-fown-archive

# public 레포지토리 생성
fown make-fown-archive --public
```

<h3 id="레이블-동기화">레이블 동기화</h3>  

```bash
# 기본 레이블로 동기화
fown labels sync

# 아카이브 레포지토리에서 동기화
fown labels sync --archive
```

<h3 id="스크립트-관리">스크립트 관리</h3>  

```bash
# 스크립트 실행
fown script use

# 스크립트 추가 (.sh 파일만 지원)
fown script add <script-file.sh>

# 스크립트 다운로드
fown script load

# 스크립트 삭제
fown script delete
```

<h3 id="파일-관리">파일 관리<h3>  

```bash
# 파일 추가
fown file add <파일이름 or 폴더이름>

# 파일 다운로드
fown file load

# 파일 삭제
fown file delete
```


<h2 id="기능">기능</h2>

- GitHub 레이블 생성, 업데이트, 동기화
- GitHub 프로젝트 자동 관리
- 설정 파일을 통한 일괄 작업
- 빠르고 간단한 설정
- GitHub CLI (`gh`) 기반 동작

<h3 id="auth">auth</h3>

- GitHub 인증

---

- Github login

```bash
# Github 로그인
fown auth login
```

- Github logout

```bash
# Github 로그아웃
fown auth logout
```

- 인증 상태
  
```bash
# 로그인 상태
fown auth status
```

<h3 id="file">file</h3>

- 기본 레포지토리에서 파일 관리

---

```bash
# 기본 레포지토리에 파일저장
fown file add <filename>
```

```bash
# 기본 레포지토리에서 파일 다운로드
fown file load
```

```bash
# 기본 레포지토리에서 파일삭제
fown file delete
```

<h3 id="make-fown-archive">make-fown-archive</h3>

- 로그인한 유저의 깃허브 레포지토리에 기본 레포지토리 생성
  
---

```bash
# 기본 레포지토리 생성
fown make-fown-archive
```


<h2 id="요구사항">요구사항</h2>  

- Python 3.12 이상

<h2 id="문서">문서</h2>  

- [테스트 서버 PyPI](https://test.pypi.org/project/fown/)
- [메인 서버 PyPI](https://pypi.org/project/fown/)
- [GitHub](https://github.com/bamjun/fown)

<h2 id="라이선스">라이선스</h2>  

MIT License
