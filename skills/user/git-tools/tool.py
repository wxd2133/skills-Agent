"""
Git 操作技能 - 仅允许在项目根及其子目录下执行，避免误操作其他路径。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# 项目根目录（SkillAgent），仅允许在此之下执行 git
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _resolve_repo_path(repo_path: str) -> Path | str:
    """解析并校验 repo_path 必须在项目根内。"""
    path = (repo_path or "").strip()
    if not path:
        return "错误：repo_path 不能为空。"
    try:
        p = Path(path).resolve()
        if not p.is_dir():
            return f"错误：路径不存在或不是目录: {p}"
        p.relative_to(PROJECT_ROOT)
        return p
    except ValueError:
        return f"错误：路径必须在项目内。项目根: {PROJECT_ROOT}"
    except Exception as e:
        return f"错误：{e}"


def git_status(repo_path: str) -> str:
    """
    检查 git 仓库状态。
    repo_path 须在项目根目录内。
    """
    res = _resolve_repo_path(repo_path)
    if isinstance(res, str):
        return res
    try:
        r = subprocess.run(
            ["git", "status"],
            cwd=str(res),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return r.stdout if r.returncode == 0 else f"状态检查失败：{r.stderr}"
    except subprocess.TimeoutExpired:
        return "错误：执行超时。"
    except Exception as e:
        return f"发生异常：{str(e)}"


def git_add(repo_path: str, files: str) -> str:
    """
    添加文件到暂存区。
    files 可为单个路径、空格分隔的多个路径、或 '.' 表示所有更改。
    repo_path 须在项目根目录内。
    """
    res = _resolve_repo_path(repo_path)
    if isinstance(res, str):
        return res
    files = (files or "").strip() or "."
    # 多个文件时拆成列表，避免空格被当作一个文件名
    add_args = files.split() if files != "." else ["."]
    try:
        r = subprocess.run(
            ["git", "add"] + add_args,
            cwd=str(res),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode == 0:
            return f"添加成功：{files}"
        return f"添加失败：{r.stderr}"
    except subprocess.TimeoutExpired:
        return "错误：执行超时。"
    except Exception as e:
        return f"发生异常：{str(e)}"

def git_commit(
    repo_path: str,
    commit_message: str = "",
    summarize: bool = False,
    auto_message: bool = False,
) -> str:
    """
    提交更改到本地仓库。支持自动生成提交消息或附加详细总结。
    repo_path 须在项目根目录内。
    """
    res = _resolve_repo_path(repo_path)
    if isinstance(res, str):
        return res
    try:
        summary = "无更改或获取失败"
        r = subprocess.run(
            ["git", "diff", "--staged", "--stat"],
            cwd=str(res),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0 and (r.stdout or "").strip():
            summary = r.stdout.strip()
        if auto_message and summary != "无更改或获取失败":
            first_line = summary.split("\n")[0].strip()
            commit_message = first_line or "自动提交：更改总结"
        if summarize and summary != "无更改或获取失败":
            commit_message = f"{commit_message}\n\n详细更改总结:\n{summary}"
        if not (commit_message or "").strip():
            commit_message = "提交更改"
        # 多行消息只传第一行给 -m，避免 shell 转义问题
        first_line_msg = (commit_message.strip().split("\n")[0] or "提交更改").strip()
        r2 = subprocess.run(
            ["git", "commit", "-m", first_line_msg],
            cwd=str(res),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r2.returncode == 0:
            return f"提交成功：{r2.stdout.strip()}"
        return f"提交失败：{r2.stderr}"
    except subprocess.TimeoutExpired:
        return "错误：执行超时。"
    except Exception as e:
        return f"发生异常：{str(e)}"

def git_push(repo_path: str, remote: str = "origin", branch: str | None = None) -> str:
    """
    推送提交到远程仓库。repo_path 须在项目根目录内。
    """
    res = _resolve_repo_path(repo_path)
    if isinstance(res, str):
        return res
    try:
        if not branch:
            r = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=str(res),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if r.returncode != 0:
                return f"获取当前分支失败：{r.stderr}"
            branch = r.stdout.strip()
        r2 = subprocess.run(
            ["git", "push", remote, branch],
            cwd=str(res),
            capture_output=True,
            text=True,
            timeout=120,
        )
        return f"推送成功到 {remote}/{branch}" if r2.returncode == 0 else f"推送失败：{r2.stderr}"
    except subprocess.TimeoutExpired:
        return "错误：执行超时。"
    except Exception as e:
        return f"发生异常：{str(e)}"


def git_pull(repo_path: str, remote: str = "origin", branch: str | None = None) -> str:
    """
    从远程仓库拉取更新。repo_path 须在项目根目录内。
    """
    res = _resolve_repo_path(repo_path)
    if isinstance(res, str):
        return res
    try:
        if not branch:
            r = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=str(res),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if r.returncode != 0:
                return f"获取当前分支失败：{r.stderr}"
            branch = r.stdout.strip()
        r2 = subprocess.run(
            ["git", "pull", remote, branch],
            cwd=str(res),
            capture_output=True,
            text=True,
            timeout=120,
        )
        return f"拉取成功从 {remote}/{branch}" if r2.returncode == 0 else f"拉取失败：{r2.stderr}"
    except subprocess.TimeoutExpired:
        return "错误：执行超时。"
    except Exception as e:
        return f"发生异常：{str(e)}"