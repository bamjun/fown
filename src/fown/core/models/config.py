"""
fown 데이터 모델 정의
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class Label:
    """GitHub 레이블 데이터 모델"""

    name: str
    color: str
    description: str = ""

    def to_dict(self) -> Dict:
        """레이블 객체를 딕셔너리로 변환"""
        return {"name": self.name, "color": self.color, "description": self.description}

    @classmethod
    def from_dict(cls, data: Dict) -> "Label":
        """딕셔너리에서 레이블 객체 생성"""
        return cls(
            name=data.get("name", ""),
            color=data.get("color", ""),
            description=data.get("description", ""),
        )


@dataclass
class Project:
    """GitHub 프로젝트 데이터 모델"""

    name: str
    description: str = ""

    def to_dict(self) -> Dict:
        """프로젝트 객체를 딕셔너리로 변환"""
        return {"name": self.name, "description": self.description}

    @classmethod
    def from_dict(cls, data: Dict) -> "Project":
        """딕셔너리에서 프로젝트 객체 생성"""
        return cls(name=data.get("name", ""), description=data.get("description", ""))


@dataclass
class Repository:
    """GitHub 저장소 정보 데이터 모델"""

    owner: str
    name: str
    url: str = ""

    @property
    def full_name(self) -> str:
        """저장소 전체 이름 (owner/name)"""
        return f"{self.owner}/{self.name}"

    @classmethod
    def from_url(cls, url: str) -> "Repository":
        """URL에서 저장소 정보 추출"""
        from fown.core.utils.file_io import extract_repo_info

        owner, name = extract_repo_info(url)
        return cls(owner=owner, name=name, url=url)


@dataclass
class Config:
    """설정 파일 데이터 모델"""

    labels: List[Label] = field(default_factory=list)
    projects: List[Project] = field(default_factory=list)

    @classmethod
    def load_labels(cls, file_path: str) -> List[Label]:
        """레이블 YAML 파일 로드"""
        from fown.core.utils.file_io import load_yaml

        data = load_yaml(file_path)
        if not data:
            return []
        if isinstance(data, list):
            return [Label.from_dict(item) for item in data]
        if isinstance(data, dict):
            return [Label.from_dict(item) for item in data.get("labels", [])]
        return []

    @classmethod
    def load_projects(cls, file_path: str) -> List[Project]:
        """프로젝트 설정 YAML 파일 로드"""
        from fown.core.utils.file_io import load_yaml

        data = load_yaml(file_path)
        if not data:
            return []
        if isinstance(data, list):
            return [Project.from_dict(item) for item in data]
        if isinstance(data, dict):
            return [Project.from_dict(item) for item in data.get("projects", [])]
        return []
