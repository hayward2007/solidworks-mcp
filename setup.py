"""Copy the single-source Markdown corpus into wheels without duplicating it in Git."""
from pathlib import Path
from shutil import copytree
from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithKnowledge(build_py):
    def run(self):
        super().run()
        copytree(Path(__file__).parent / "knowledge",
                 Path(self.build_lib) / "solidworks_mcp/design/resources/knowledge", dirs_exist_ok=True)


setup(cmdclass={"build_py": BuildWithKnowledge})
