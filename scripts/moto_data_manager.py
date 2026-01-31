import json
import os
import difflib
import re
import shutil
from datetime import datetime
import questionary
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule
from git import Repo
from jsonschema import validate, ValidationError

console = Console()


class MotoDataManager:
    def __init__(self, file_path):
        self.file_path = file_path
        with open(file_path, "r", encoding="utf-8") as f:
            self.raw_original = f.read()
            self.data = json.loads(self.raw_original)
        self.detected_indent = self._detect_indent(self.raw_original)
        try:
            self.repo = Repo(".", search_parent_directories=True)
        except:
            self.repo = None

    def _detect_indent(self, text):
        lines = text.splitlines()
        for line in lines:
            match = re.match(r"^([ \t]+)\S", line)
            if match:
                indent_str = match.group(1)
                return "\t" if "\t" in indent_str else len(indent_str)
        return 2

    def ensure_metadata_structure(self):
        if "metadata" not in self.data:
            self.data["metadata"] = {}
        for key in ["created_at", "updated_at"]:
            if key not in self.data["metadata"]:
                self.data["metadata"][key] = {"iso": "", "label": ""}

    def insert_displacement_class(self, value):
        """'model'キーの直後に 'displacement_class' を挿入する"""
        new_data = {}
        for k, v in self.data.items():
            new_data[k] = v
            if k == "model":
                new_data["displacement_class"] = value
        self.data = new_data

    def get_git_dates(self):
        if not self.repo:
            return None, None
        commits = list(self.repo.iter_commits(paths=self.file_path))
        if not commits:
            return None, None
        return datetime.fromtimestamp(
            commits[-1].authored_date
        ), datetime.fromtimestamp(commits[0].authored_date)

    def get_os_dates(self):
        stat = os.stat(self.file_path)
        created_at = datetime.fromtimestamp(
            getattr(stat, "st_birthtime", stat.st_ctime)
        )
        updated_at = datetime.fromtimestamp(stat.st_mtime)
        return created_at, updated_at

    def process_universal_specs(self):
        logs = []
        for item in self.data.get("timeline", []):
            eng = item.get("engine", {})
            m_code = item.get("model_code", "Unknown")
            if eng.get("bore_mm") and eng.get("stroke_mm"):
                ratio = round(eng["bore_mm"] / eng["stroke_mm"], 2)
                if eng.get("bore_stroke_ratio") != ratio:
                    eng["bore_stroke_ratio"] = ratio
                    logs.append(f"[{m_code}] Ratio: {ratio}")
            if eng.get("ps") and not eng.get("kw"):
                kw = int(eng["ps"] * 0.7355)
                eng["kw"] = kw
                logs.append(f"[{m_code}] Power: {kw}kW")
        return logs

    def get_formatted_json(self):
        content = json.dumps(
            self.data, indent=self.detected_indent, ensure_ascii=False, sort_keys=False
        )
        pattern = r'\[\s+((?:(?:"[^"]*"|[\d\.]+|null|true|false),\s*)*(?:"[^"]*"|[\d\.]+|null|true|false|))\s+\]'
        content = re.sub(
            pattern,
            lambda m: "[" + re.sub(r"\s+", " ", m.group(1)).strip() + "]",
            content,
        )
        return content + "\n"

    def validate_schema(self, schema_path="schema.json"):
        if not os.path.exists(schema_path):
            return True, "Schema missing"
        try:
            v_data = self.data.copy()
            v_data.pop("$schema", None)
            validate(
                instance=v_data,
                schema=json.load(open(schema_path, "r", encoding="utf-8")),
            )
            return True, "Valid"
        except ValidationError as e:
            path = ".".join([str(p) for p in e.path])
            return False, f"At {path}: {e.message}"

    def show_diff(self):
        new_content = self.get_formatted_json()
        diff = list(
            difflib.unified_diff(
                self.raw_original.splitlines(),
                new_content.splitlines(),
                fromfile="Original",
                tofile="New",
                lineterm="",
            )
        )
        if not diff:
            return False
        for line in diff:
            if line.startswith("+"):
                console.print(f"[green]{line}[/green]")
            elif line.startswith("-"):
                console.print(f"[red]{line}[/red]")
            else:
                console.print(line)
        return True

    def save(self):
        formatted = self.get_formatted_json()
        bak_path = self.file_path + ".bak"
        shutil.copy2(self.file_path, bak_path)
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(formatted)
            os.remove(bak_path)
        except Exception as e:
            shutil.move(bak_path, self.file_path)
            raise e


def parse_iso(iso_str):
    if not iso_str:
        return "-"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", ""))
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return "Invalid"


def format_meta(dt):
    return (
        {"iso": dt.isoformat() + "Z", "label": dt.strftime("%Y-%m-%d %H:%M")}
        if dt
        else None
    )


def main():
    console.print(Rule(style="cyan"))
    console.print(
        "[bold cyan]MOTO DATA MANAGER[/bold cyan] [dim]v2.7[/dim]", justify="center"
    )
    console.print(Rule(style="cyan"))

    data_root = "./data"
    json_files = [
        os.path.join(r, f)
        for r, d, fs in os.walk(data_root)
        for f in fs
        if f.endswith(".json") and f != "schema.json"
    ]
    if not json_files:
        return

    target_file = questionary.select("ファイルを選択:", choices=json_files).ask()
    if not target_file:
        return

    manager = MotoDataManager(target_file)
    manager.ensure_metadata_structure()

    git_c, git_u = manager.get_git_dates()
    os_c, os_u = manager.get_os_dates()
    now = datetime.now()
    meta = manager.data.get("metadata", {})

    # 1. 健康診断
    status_table = Table(box=None, header_style="bold cyan")
    status_table.add_column("Property", width=12)
    status_table.add_column("Handwritten (Label)")
    status_table.add_column("Internal (ISO)")
    status_table.add_column("Status")
    mismatch = False
    for key, name in [("created_at", "Created"), ("updated_at", "Updated")]:
        l, i = meta.get(key, {}).get("label", "-"), meta.get(key, {}).get("iso", "")
        parsed = parse_iso(i)
        is_ok = l == parsed
        status_table.add_row(
            name,
            l,
            f"[red]{parsed}[/]" if not is_ok else parsed,
            "[green]✔ OK[/]" if is_ok else "[bold red]✘ MISMATCH[/]",
        )
        if not is_ok:
            mismatch = True
    console.print(
        Panel(
            status_table,
            title="[bold white]JSON Integrity Check[/bold white]",
            border_style="cyan",
        )
    )

    # 2. リファレンス表示
    ref_table = Table(box=None, header_style="dim")
    ref_table.add_column("Source", width=15)
    ref_table.add_column("Created")
    ref_table.add_column("Updated")
    ref_table.add_row(
        "Git History",
        git_c.strftime("%y-%m-%d %H:%M") if git_c else "-",
        git_u.strftime("%y-%m-%d %H:%M") if git_u else "-",
    )
    ref_table.add_row(
        "File System (OS)",
        f"[yellow]{os_c.strftime('%y-%m-%d %H:%M')}[/]",
        os_u.strftime("%y-%m-%d %H:%M"),
    )
    console.print(
        Panel(ref_table, title="[dim]Reference Timelines[/dim]", border_style="dim")
    )

    # 3. スペック計算 & 同期
    spec_logs = manager.process_universal_specs()
    if spec_logs:
        console.print(
            Panel(
                "\n".join(spec_logs),
                title="[cyan]Calculated Fields[/cyan]",
                border_style="cyan",
            )
        )

    if mismatch and questionary.confirm("ISOの不一致を自動同期しますか？").ask():
        for k in ["created_at", "updated_at"]:
            l = meta.get(k, {}).get("label")
            if l:
                meta[k]["iso"] = (
                    datetime.strptime(l, "%Y-%m-%d %H:%M").isoformat() + "Z"
                )

    # 4. 新規項目の補完 (displacement_class / categories)
    if "displacement_class" not in manager.data:
        class_choices = [
            questionary.Choice(str(c), value=c)
            for c in [50, 125, 250, 400, 750, 1000, 1100]
        ]
        val = questionary.select(
            "displacement_classを選択 (model直下に挿入):", choices=class_choices
        ).ask()
        manager.insert_displacement_class(val)

    # 各タイムラインのカテゴリーチェック
    category_list = [
        "ネイキッド",
        "スーパースポーツ",
        "レーサーレプリカ",
        "アメリカン",
        "ネオクラシック",
        "スクーター",
        "ミニバイク",
        "モタード",
        "アドベンチャー",
        "ツアラー",
        "オフロード",
        "スポーツツアラー",
        "ストリート",
        "ビジネス",
    ]

    for item in manager.data.get("timeline", []):
        basic = item.get("basic_info", {})
        if "categories" not in basic or not basic["categories"]:
            m_code = item.get("model_code", "Unknown")
            console.print(f"[yellow]⚠ カテゴリー未設定: {m_code}[/yellow]")
            selected = questionary.checkbox(
                f"[{m_code}] カテゴリーを複数選択 (スペースで選択/解除):",
                choices=category_list,
            ).ask()
            basic["categories"] = selected

    # 5. 保存
    valid, msg = manager.validate_schema()
    if not valid:
        console.print(
            Panel(
                msg, title="[bold red]Validation Failed[/bold red]", border_style="red"
            )
        )
        if not questionary.confirm("保存を強行しますか？").ask():
            return

    if manager.show_diff():
        if questionary.confirm("変更を保存しますか？").ask():
            manager.save()
            console.print("[bold green]✨ Data safely synchronized![/bold green]")


if __name__ == "__main__":
    main()
