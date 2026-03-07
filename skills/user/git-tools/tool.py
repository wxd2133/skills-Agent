import subprocess
import os

def git_status(repo_path: str) -> str:
    """
    检查git仓库状态。
    
    Args:
        repo_path: git仓库的路径
    
    Returns:
        字符串，显示状态信息或错误。
    """
    try:
        if not os.path.isdir(repo_path):
            return f"错误：路径 '{repo_path}' 不存在或不是目录。"
        original_cwd = os.getcwd()
        os.chdir(repo_path)
        result = subprocess.run(["git", "status"], capture_output=True, text=True)
        os.chdir(original_cwd)
        if result.returncode == 0:
            return result.stdout
        else:
            return f"状态检查失败：{result.stderr}"
    except Exception as e:
        return f"发生异常：{str(e)}"

def git_add(repo_path: str, files: str) -> str:
    """
    添加文件到暂存区。
    
    Args:
        repo_path: git仓库的路径
        files: 要添加的文件路径，多个文件用空格分隔，或使用通配符如'.'表示所有更改
    
    Returns:
        字符串，表示添加结果或错误。
    """
    try:
        if not os.path.isdir(repo_path):
            return f"错误：路径 '{repo_path}' 不存在或不是目录。"
        original_cwd = os.getcwd()
        os.chdir(repo_path)
        result = subprocess.run(["git", "add", files], capture_output=True, text=True)
        os.chdir(original_cwd)
        if result.returncode == 0:
            return f"添加成功：{files}"
        else:
            return f"添加失败：{result.stderr}"
    except Exception as e:
        return f"发生异常：{str(e)}"

def git_commit(repo_path: str, commit_message: str, summarize: bool = False) -> str:
    """
    提交更改到本地仓库。支持在提交消息中自动总结更改。
    
    Args:
        repo_path: git仓库的路径
        commit_message: 提交消息
        summarize: 是否在提交消息中总结更改，默认为False
    
    Returns:
        字符串，表示提交结果或错误。
    """
    try:
        if not os.path.isdir(repo_path):
            return f"错误：路径 '{repo_path}' 不存在或不是目录。"
        original_cwd = os.getcwd()
        os.chdir(repo_path)
        
        if summarize:
            # 获取暂存区的更改总结
            summary_result = subprocess.run(["git", "diff", "--staged", "--stat"], capture_output=True, text=True)
            if summary_result.returncode == 0 and summary_result.stdout.strip():
                summary = summary_result.stdout.strip()
                commit_message = f"{commit_message}\n\n更改总结:\n{summary}"
            else:
                # 如果没有更改或获取失败，保持原消息
                pass
        
        result = subprocess.run(["git", "commit", "-m", commit_message], capture_output=True, text=True)
        os.chdir(original_cwd)
        if result.returncode == 0:
            return f"提交成功：{result.stdout.strip()}"
        else:
            return f"提交失败：{result.stderr}"
    except Exception as e:
        return f"发生异常：{str(e)}"

def git_push(repo_path: str, remote: str = "origin", branch: str = None) -> str:
    """
    推送提交到远程仓库。
    
    Args:
        repo_path: git仓库的路径
        remote: 远程仓库名称，默认为'origin'
        branch: 要推送的分支，默认为当前分支
    
    Returns:
        字符串，表示推送结果或错误。
    """
    try:
        if not os.path.isdir(repo_path):
            return f"错误：路径 '{repo_path}' 不存在或不是目录。"
        original_cwd = os.getcwd()
        os.chdir(repo_path)
        if branch is None:
            # 获取当前分支
            branch_result = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
            if branch_result.returncode != 0:
                os.chdir(original_cwd)
                return f"获取当前分支失败：{branch_result.stderr}"
            branch = branch_result.stdout.strip()
        result = subprocess.run(["git", "push", remote, branch], capture_output=True, text=True)
        os.chdir(original_cwd)
        if result.returncode == 0:
            return f"推送成功到 {remote}/{branch}"
        else:
            return f"推送失败：{result.stderr}"
    except Exception as e:
        return f"发生异常：{str(e)}"

def git_pull(repo_path: str, remote: str = "origin", branch: str = None) -> str:
    """
    从远程仓库拉取更新。
    
    Args:
        repo_path: git仓库的路径
        remote: 远程仓库名称，默认为'origin'
        branch: 要拉取的分支，默认为当前分支
    
    Returns:
        字符串，表示拉取结果或错误。
    """
    try:
        if not os.path.isdir(repo_path):
            return f"错误：路径 '{repo_path}' 不存在或不是目录。"
        original_cwd = os.getcwd()
        os.chdir(repo_path)
        if branch is None:
            # 获取当前分支
            branch_result = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
            if branch_result.returncode != 0:
                os.chdir(original_cwd)
                return f"获取当前分支失败：{branch_result.stderr}"
            branch = branch_result.stdout.strip()
        result = subprocess.run(["git", "pull", remote, branch], capture_output=True, text=True)
        os.chdir(original_cwd)
        if result.returncode == 0:
            return f"拉取成功从 {remote}/{branch}"
        else:
            return f"拉取失败：{result.stderr}"
    except Exception as e:
        return f"发生异常：{str(e)}"