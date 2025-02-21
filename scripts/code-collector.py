#!/usr/bin/env python
import os
import sys
import argparse
import io

try:
    import pathspec
except ImportError:
    sys.exit("缺少 pathspec 库，请先执行 pip install pathspec")


def load_gitignore_spec(gitignore_path):
    """加载 .gitignore 文件并编译匹配规则"""
    with io.open(gitignore_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def should_ignore(rel_path, spec, extra_ignore_files, extra_ignore_extensions):
    """
    根据 .gitignore 规则、额外忽略的文件或目录名称和后缀判断是否应忽略。
    参数：
      - rel_path: 文件或目录相对于目标目录的路径
      - spec: pathspec 对象，可能为 None
      - extra_ignore_files: 忽略的文件或目录名称集合
      - extra_ignore_extensions: 忽略的文件后缀集合
    """
    if os.path.basename(rel_path) in extra_ignore_files:
        return True
    if any(rel_path.endswith(ext) for ext in extra_ignore_extensions):
        return True
    if spec and spec.match_file(rel_path):
        return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="整理项目代码到一个Markdown文件中，支持 .gitignore、额外过滤规则，默认写入项目目录树。"
    )
    parser.add_argument("target_directory", help="项目的目标目录")
    parser.add_argument("output_file", help="输出文件路径")
    parser.add_argument(
        "--no-tree",
        action="store_true",
        help="如果设置，则不在输出文件中包含项目目录树",
    )
    parser.add_argument(
        "--ignore-files", nargs="*", default=[], help="指定忽略的文件或目录名称列表"
    )
    parser.add_argument(
        "--ignore-extensions",
        nargs="*",
        default=[],
        help="指定忽略的文件后缀列表（例如：.log .tmp）",
    )
    args = parser.parse_args()

    target_dir = os.path.abspath(args.target_directory)
    output_file = os.path.abspath(args.output_file)
    extra_ignore_files = set(args.ignore_files)
    extra_ignore_extensions = set(args.ignore_extensions)

    if not os.path.isdir(target_dir):
        sys.exit("目标目录不存在或不是一个目录。")

    # 如果是 Git 仓库，自动忽略 .git 目录
    git_dir = os.path.join(target_dir, ".git")
    if os.path.isdir(git_dir):
        extra_ignore_files.add(".git")

    # 如果存在 .gitignore 文件，则加载规则
    gitignore_path = os.path.join(target_dir, ".gitignore")
    spec = None
    if os.path.isfile(gitignore_path):
        spec = load_gitignore_spec(gitignore_path)

    # 内嵌生成目录树的函数（类似 tree 命令输出）
    def generate_tree(root, current_rel="", prefix=""):
        full_path = os.path.join(root, current_rel)
        try:
            entries = sorted(os.listdir(full_path))
        except Exception as e:
            return []
        filtered_entries = []
        for entry in entries:
            entry_rel = os.path.join(current_rel, entry) if current_rel else entry
            if should_ignore(
                entry_rel, spec, extra_ignore_files, extra_ignore_extensions
            ):
                continue
            filtered_entries.append(entry)
        tree_lines = []
        count = len(filtered_entries)
        for index, entry in enumerate(filtered_entries):
            connector = "└── " if index == count - 1 else "├── "
            line = prefix + connector + entry
            tree_lines.append(line)
            entry_rel = os.path.join(current_rel, entry) if current_rel else entry
            full_entry_path = os.path.join(root, entry_rel)
            if os.path.isdir(full_entry_path):
                extension = "    " if index == count - 1 else "│   "
                tree_lines.extend(generate_tree(root, entry_rel, prefix + extension))
        return tree_lines

    # 获取目标目录的最后一级名称（若传入的是"."，则根据绝对路径获取最后一级）
    target_dir_name = os.path.basename(os.path.normpath(target_dir))

    with io.open(output_file, "w", encoding="utf-8") as outf:
        # 写入描述信息（英文）
        description = (
            f"This markdown file consolidates the project directory structure and source code contents for analysis by a large language model.\n"
            f"Target project directory: '{target_dir_name}'.\n"
            f"Each file's content is enclosed in its own markdown code block for better clarity.\n"
        )
        outf.write(description + "\n\n")

        # 如果未设置--no-tree，则写入目录树部分，单独用代码块包裹
        if not args.no_tree:
            outf.write("#### Project Directory Tree\n\n")
            outf.write("```\n")
            tree_lines = generate_tree(target_dir)
            for line in tree_lines:
                outf.write(line + "\n")
            outf.write("```\n\n")

        # 遍历目标目录，将每个文件的路径及内容写入，文件内容各自放在独立的Markdown代码块中
        for root, dirs, files in os.walk(target_dir):
            # 排除不需要遍历的目录
            dirs[:] = [d for d in dirs if d not in extra_ignore_files]
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, target_dir)

                if should_ignore(
                    rel_path, spec, extra_ignore_files, extra_ignore_extensions
                ):
                    continue

                try:
                    with io.open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception as e:
                    print(f"Skipping file {rel_path}, reason: {e}")
                    continue

                # 写入文件相对路径描述
                outf.write(f"===== {rel_path} =====\n")
                # 用独立的Markdown代码块包裹文件内容
                outf.write("```\n")
                outf.write(content)
                outf.write("\n```\n\n")


if __name__ == "__main__":
    main()
