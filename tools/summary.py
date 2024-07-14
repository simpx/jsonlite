import os
import ast
import json

# 用于解析和总结Python文件
def parse_python_file(file_path):
    with open(file_path, "r") as file:
        try:
            tree = ast.parse(file.read(), filename=file_path)
        except SyntaxError as e:
            print(f"Syntax error in {file_path}: {e}")
            return None

    summary = {
        "classes": [],
        "functions": [],
        "docstring": ast.get_docstring(tree)
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            summary["functions"].append({
                "name": node.name,
                "lineno": node.lineno,
                "docstring": ast.get_docstring(node),
                "parameters": [arg.arg for arg in node.args.args],
                "code_snippet": "\n".join([ast.unparse(node).split("\n")[i] for i in range(min(3, len(ast.unparse(node).split("\n"))))])
            })
        elif isinstance(node, ast.ClassDef):
            summary["classes"].append({
                "name": node.name,
                "lineno": node.lineno,
                "docstring": ast.get_docstring(node),
                "attributes": [n.targets[0].id for n in node.body if isinstance(n, ast.Assign)],
                "methods": [parse_python_function(n) for n in node.body if isinstance(n, ast.FunctionDef)],
                "code_snippet": "\n".join([ast.unparse(node).split("\n")[i] for i in range(min(3, len(ast.unparse(node).split("\n"))))])
            })

    return summary

def parse_python_function(node):
    return {
        "name": node.name,
        "lineno": node.lineno,
        "docstring": ast.get_docstring(node),
        "parameters": [arg.arg for arg in node.args.args],
        "code_snippet": "\n".join([ast.unparse(node).split("\n")[i] for i in range(min(3, len(ast.unparse(node).split("\n"))))])
    }

# 生成目录结构的ASCII图
def generate_ascii_tree(root_dir, prefix=""):
    tree_lines = []
    contents = sorted(os.listdir(root_dir))
    pointers = [ "├── " ] * (len(contents) - 1) + [ "└── " ]
    for pointer, path in zip(pointers, contents):
        full_path = os.path.join(root_dir, path)
        if os.path.isdir(full_path) and not path.endswith('_env') and not path.endswith('egg-info') and path not in [".git", "__pycache__", "venv", "env", ".github", ".pytest_cache", ".benchmarks"]:
            tree_lines.append(prefix + pointer + path)
            tree_lines.extend(generate_ascii_tree(full_path, prefix + ("│   " if pointer == "├── " else "    ")))
        elif path.endswith(".py") or path in ["requirements.txt", "README.md", "setup.py"]:
            tree_lines.append(prefix + pointer + path)
    return tree_lines

# 遍历项目目录，生成摘要
def summarize_directory(root_dir):
    project_summary = {
        "files": {},
        "ascii_tree": generate_ascii_tree(root_dir)
    }
    
    for subdir, _, files in os.walk(root_dir):
        # 跳过一些与代码无关的目录和文件
        if any(x in subdir for x in [".git", "__pycache__", "venv", "env"]) or subdir.endswith('_env'):
            continue

        for file in files:
            file_path = os.path.join(subdir, file)
            if file.endswith(".py"):
                file_summary = parse_python_file(file_path)
                if file_summary:
                    project_summary["files"][file_path] = {
                        "type": "python",
                        "summary": file_summary,
                        "content": open(file_path).read()
                    }
            elif file in ["requirements.txt", "README.md", "setup.py"]:
                with open(file_path, "r") as f:
                    project_summary["files"][file_path] = {
                        "type": "text",
                        "content": f.read()
                    }

    return project_summary

# 生成对ChatGPT友好的Markdown摘要
def generate_markdown_summary(project_summary):
    summary_lines = ["# PROJECT SUMMARY\n"]

    # 生成目录结构的ASCII图
    summary_lines.append("## Directory Layout\n")
    summary_lines.append("```")
    summary_lines.extend(project_summary["ascii_tree"])
    summary_lines.append("```\n")
    
    # 生成文件内容
    summary_lines.append("## Files Summary\n")
    for file_path, content in project_summary["files"].items():
        summary_lines.append(f"<details><summary>File: `{file_path}`</summary>\n")
        
        if content["type"] == "python":
            summary_lines.append("<h4>AST Summary</h4>")
            summary_lines.append("<pre>")
            summary_lines.append(json.dumps(content["summary"], indent=4))
            summary_lines.append("</pre>\n")

            summary_lines.append("<h4>Code</h4>")
            summary_lines.append("<pre><code class=\"language-python\">")
            summary_lines.append(content["content"])
            summary_lines.append("</code></pre>\n")
        else:
            summary_lines.append("<h4>Content</h4>")
            summary_lines.append("<pre>")
            summary_lines.append(content["content"])
            summary_lines.append("</pre>\n")
        
        summary_lines.append("</details>\n")

    return "\n".join(summary_lines)

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python summary_code.py <root_directory>")
        sys.exit(1)

    root_dir = sys.argv[1]
    project_summary = summarize_directory(root_dir)
    markdown_summary = generate_markdown_summary(project_summary)
    
    # 输出Markdown摘要到文件
    with open("project_summary.md", "w") as f:
        f.write(markdown_summary)

    print(markdown_summary)

