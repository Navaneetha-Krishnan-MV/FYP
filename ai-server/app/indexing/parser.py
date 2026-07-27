import os
from typing import List, Dict, Any, Optional
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

PY_LANG = Language(tspython.language())
JS_LANG = Language(tsjs.language())
TS_LANG = Language(tsts.language_typescript())
JAVA_LANG = Language(tsjava.language())

LANG_MAP = {
    "python": PY_LANG,
    "javascript": JS_LANG,
    "typescript": TS_LANG,
    "java": JAVA_LANG,
}

class CodeChunkData:
    def __init__(
        self,
        file_path: str,
        language: str,
        chunk_type: str,
        function_name: str,
        code_content: str,
        start_line: int,
        end_line: int,
        class_name: Optional[str] = None,
        signature: Optional[str] = None,
        imports: Optional[List[str]] = None,
        calls: Optional[List[str]] = None,
    ):
        self.file_path = file_path
        self.language = language
        self.chunk_type = chunk_type
        self.function_name = function_name
        self.code_content = code_content
        self.start_line = start_line
        self.end_line = end_line
        self.class_name = class_name
        self.signature = signature
        self.imports = imports or []
        self.calls = calls or []

def parse_file(file_path: str, repo_root: str) -> List[CodeChunkData]:
    rel_path = os.path.relpath(file_path, repo_root)
    ext = os.path.splitext(file_path)[1].lower()

    lang_name = None
    if ext == ".py":
        lang_name = "python"
    elif ext in [".js", ".jsx"]:
        lang_name = "javascript"
    elif ext in [".ts", ".tsx"]:
        lang_name = "typescript"
    elif ext == ".java":
        lang_name = "java"
    else:
        return []

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return []

    if not code.trim() if hasattr(code, 'trim') else not code.strip():
        return []

    ts_lang = LANG_MAP[lang_name]
    parser = Parser(ts_lang)
    tree = parser.parse(bytes(code, "utf-8"))
    root_node = tree.root_node

    file_imports = extract_imports(root_node, lang_name, code)
    chunks = extract_chunks(root_node, rel_path, lang_name, code, file_imports)
    
    # Fallback if no functions/classes found: create a module chunk
    if not chunks and code.strip():
        lines = code.splitlines()
        chunks.append(CodeChunkData(
            file_path=rel_path,
            language=lang_name,
            chunk_type="module",
            function_name=os.path.basename(file_path),
            code_content=code[:2000], # max 2000 chars for module chunk
            start_line=1,
            end_line=len(lines),
            class_name=None,
            signature=f"file:{rel_path}",
            imports=file_imports,
            calls=[]
        ))

    return chunks

def extract_imports(node, lang: str, code: str) -> List[str]:
    imports = []
    code_bytes = bytes(code, "utf-8")

    def traverse(n):
        if lang == "python":
            if n.type in ["import_statement", "import_from_statement"]:
                text = code_bytes[n.start_byte:n.end_byte].decode("utf-8", "ignore")
                imports.append(text.strip())
        elif lang in ["javascript", "typescript"]:
            if n.type == "import_statement":
                text = code_bytes[n.start_byte:n.end_byte].decode("utf-8", "ignore")
                imports.append(text.strip())
        elif lang == "java":
            if n.type == "import_declaration":
                text = code_bytes[n.start_byte:n.end_byte].decode("utf-8", "ignore")
                imports.append(text.strip())

        for child in n.children:
            traverse(child)

    traverse(node)
    return list(set(imports))

def extract_calls(node, lang: str, code: str) -> List[str]:
    calls = []
    code_bytes = bytes(code, "utf-8")

    def traverse(n):
        if lang == "python" and n.type == "call":
            func_node = n.child_by_field_name("function")
            if func_node:
                text = code_bytes[func_node.start_byte:func_node.end_byte].decode("utf-8", "ignore")
                calls.append(text.split(".")[-1]) # get leaf call name
        elif lang in ["javascript", "typescript"] and n.type == "call_expression":
            func_node = n.child_by_field_name("function")
            if func_node:
                text = code_bytes[func_node.start_byte:func_node.end_byte].decode("utf-8", "ignore")
                calls.append(text.split(".")[-1])
        elif lang == "java" and n.type == "method_invocation":
            name_node = n.child_by_field_name("name")
            if name_node:
                text = code_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", "ignore")
                calls.append(text)

        for child in n.children:
            traverse(child)

    traverse(node)
    return list(set(calls))

def extract_chunks(node, rel_path: str, lang: str, code: str, file_imports: List[str]) -> List[CodeChunkData]:
    chunks = []
    code_bytes = bytes(code, "utf-8")

    def get_node_text(n):
        return code_bytes[n.start_byte:n.end_byte].decode("utf-8", "ignore")

    def walk(n, current_class=None):
        nonlocal chunks

        # Python class
        if lang == "python" and n.type == "class_definition":
            name_node = n.child_by_field_name("name")
            class_name = get_node_text(name_node) if name_node else "UnknownClass"
            for child in n.children:
                walk(child, current_class=class_name)
            return

        # Python function / method
        if lang == "python" and n.type == "function_definition":
            name_node = n.child_by_field_name("name")
            func_name = get_node_text(name_node) if name_node else "anonymous"
            params_node = n.child_by_field_name("parameters")
            sig = f"def {func_name}{get_node_text(params_node) if params_node else '()'}"
            content = get_node_text(n)
            calls = extract_calls(n, lang, code)

            chunks.append(CodeChunkData(
                file_path=rel_path,
                language=lang,
                chunk_type="method" if current_class else "function",
                function_name=func_name,
                code_content=content,
                start_line=n.start_point[0] + 1,
                end_line=n.end_point[0] + 1,
                class_name=current_class,
                signature=sig,
                imports=file_imports,
                calls=calls
            ))
            return

        # JS/TS class
        if lang in ["javascript", "typescript"] and n.type in ["class_declaration", "class"]:
            name_node = n.child_by_field_name("name")
            class_name = get_node_text(name_node) if name_node else "UnknownClass"
            for child in n.children:
                walk(child, current_class=class_name)
            return

        # JS/TS function / method / arrow function
        if lang in ["javascript", "typescript"] and n.type in ["function_declaration", "method_definition", "arrow_function", "function_expression"]:
            func_name = "anonymous"
            name_node = n.child_by_field_name("name")
            if name_node:
                func_name = get_node_text(name_node)
            elif n.parent and n.parent.type in ["variable_declarator", "pair"]:
                var_name = n.parent.child_by_field_name("name") or n.parent.child_by_field_name("key")
                if var_name:
                    func_name = get_node_text(var_name)

            content = get_node_text(n)
            calls = extract_calls(n, lang, code)

            chunks.append(CodeChunkData(
                file_path=rel_path,
                language=lang,
                chunk_type="method" if current_class else "function",
                function_name=func_name,
                code_content=content,
                start_line=n.start_point[0] + 1,
                end_line=n.end_point[0] + 1,
                class_name=current_class,
                signature=f"{func_name}()",
                imports=file_imports,
                calls=calls
            ))
            return

        # Java class
        if lang == "java" and n.type == "class_declaration":
            name_node = n.child_by_field_name("name")
            class_name = get_node_text(name_node) if name_node else "UnknownClass"
            for child in n.children:
                walk(child, current_class=class_name)
            return

        # Java method
        if lang == "java" and n.type in ["method_declaration", "constructor_declaration"]:
            name_node = n.child_by_field_name("name")
            func_name = get_node_text(name_node) if name_node else "Constructor"
            content = get_node_text(n)
            calls = extract_calls(n, lang, code)

            chunks.append(CodeChunkData(
                file_path=rel_path,
                language=lang,
                chunk_type="method" if current_class else "function",
                function_name=func_name,
                code_content=content,
                start_line=n.start_point[0] + 1,
                end_line=n.end_point[0] + 1,
                class_name=current_class,
                signature=f"{func_name}()",
                imports=file_imports,
                calls=calls
            ))
            return

        for child in n.children:
            walk(child, current_class)

    walk(node)
    return chunks
