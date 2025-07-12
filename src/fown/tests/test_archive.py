"""
아카이브 기능 테스트
"""

import os
import shutil
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from fown.cli.archive import make_archive


class TestArchive(TestCase):
    """아카이브 기능 테스트 클래스"""

    def setUp(self):
        """테스트 설정"""
        self.runner = CliRunner()
        self.test_output_dir = Path("./test_archives")

        # 테스트 디렉토리 생성
        if not self.test_output_dir.exists():
            self.test_output_dir.mkdir()

    def tearDown(self):
        """테스트 정리"""
        # 테스트 디렉토리 삭제
        if self.test_output_dir.exists():
            shutil.rmtree(self.test_output_dir)

    @patch("fown.cli.archive.get_git_repo_url")
    @patch("fown.cli.archive.Repository.from_url")
    def test_make_archive_basic(self, mock_from_url, mock_get_repo_url):
        """기본 아카이브 생성 테스트"""
        # Mock 설정
        mock_get_repo_url.return_value = "https://github.com/test/repo"
        mock_repo = MagicMock()
        mock_repo.owner = "test"
        mock_repo.name = "repo"
        mock_repo.full_name = "test/repo"
        mock_from_url.return_value = mock_repo

        # 명령 실행
        result = self.runner.invoke(make_archive, ["--output-dir", str(self.test_output_dir)])

        # 검증
        self.assertEqual(result.exit_code, 0)

        # 아카이브 디렉토리가 생성되었는지 확인
        archives = list(self.test_output_dir.glob("test_repo_*"))
        self.assertGreater(len(archives), 0)
