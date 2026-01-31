import json
import os
import difflib
import re
from datetime import datetime
import questionary
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from git import Repo
from jsonschema import validate, ValidationError

console = Console()


class MotoDataManager:
    """
    バイクデータの品質管理クラス。
    スペック計算、アセット検証、メタデータの整合性（ISO/Label）チェックを行う。
    """

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
        """現在のファイルからインデント設定を推測する"""
        lines = text.splitlines()
        for line in lines:
            match = re.match(r"^([ \t]+)\S", line)
            if match:
                indent_str = match.group(1)
                return "\t" if "\t" in indent_str else len(indent_str)
        return 2

    def get_git_dates(self):
        """Gitの履歴から『最初』と『最新』のコミット日時を取得する"""
        if not self.repo:
            return None, None
        commits = list(self.repo.iter_commits(paths=self.file_path))
        if not commits:
            return None, None
        created_at = datetime.fromtimestamp(commits[-1].authored_date)
        updated_at = datetime.fromtimestamp(commits[0].authored_date)
        return created_at, updated_at

    def get_os_dates(self):
        """OSの統計情報を取得（コピーなどで作成日がズレる可能性に注意）"""
        stat = os.stat(self.file_path)
        created_at = datetime.fromtimestamp(
            getattr(stat, "st_birthtime", stat.st_ctime)
        )
        updated_at = datetime.fromtimestamp(stat.st_mtime)
        return created_at, updated_at

    def process_universal_specs(self):
        """全車種共通のスペック計算と、ISO/Labelの矛盾チェックを行う"""
        logs = []
        warnings = []

        # 1. 数値スペックの計算
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

        # 2. メタデータのISO/Label整合性チェック
        meta = self.data.get("metadata", {})
        for key in ["created_at", "updated_at"]:
            dt_info = meta.get(key, {})
            iso_val = dt_info.get("iso")
            label_val = dt_info.get("label")
            if iso_val and label_val:
                # ISOからパースした日時とLabelを比較（分単位まで）
                try:
                    iso_dt = datetime.fromisoformat(iso_val.replace("Z", ""))
                    label_dt = datetime.strptime(label_val, "%Y-%m-%d %H:%M")
                    if iso_dt.strftime("%Y-%m-%d %H:%M") != label_val:
                        warnings.append(
                            f"Date Mismatch ({key}): ISOとLabelが一致しません。修正が必要です。"
                        )
                except ValueError:
                    warnings.append(
                        f"Format Error ({key}): 日付の形式が正しくありません。"
                    )

        return logs, warnings

    def get_formatted_json(self):
        """配列をコンパクトに整形したJSON文字列を生成する"""
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
        """構造バリデーション"""
        if not os.path.exists(schema_path):
            return True, "Schema missing"
        try:
            v_data = self.data.copy()
            v_data.pop("$schema", None)
            validate(
                instance=v_data,
                schema=json.load(open(schema_path, "r", encoding="utf-8")),
            )
            return True, "Success"
        except ValidationError as e:
            return False, e.message

    def show_diff(self):
        """差分表示"""
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
            console.print("[yellow]変更はありません。[/yellow]")
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
        """保存"""
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write(self.get_formatted_json())


def format_meta(dt):
    return (
        {"iso": dt.isoformat() + "Z", "label": dt.strftime("%Y-%m-%d %H:%M")}
        if dt
        else None
    )


def main():
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

    # 1. 自動計算と整合性警告
    logs, warnings = manager.process_universal_specs()
    if logs:
        console.print(Panel("\n".join(logs), title="Calculated", border_style="cyan"))
    if warnings:
        console.print(
            Panel(
                "\n".join(warnings),
                title="Consistency Warnings",
                border_style="bold yellow",
            )
        )

    # 2. メタデータソース収集
    git_c, git_u = manager.get_git_dates()
    os_c, _ = manager.get_os_dates()
    now = datetime.now()
    meta = manager.data.get("metadata", {})

    table = Table(title=f"Metadata Analysis: {target_file}")
    table.add_column("Source", style="bold")
    table.add_column("Created At (作成)", style="green")
    table.add_column("Updated At (更新)", style="magenta")
    table.add_row(
        "手書き情報 (JSON)",
        meta.get("created_at", {}).get("label", "-"),
        meta.get("updated_at", {}).get("label", "-"),
    )
    if git_c:
        table.add_row(
            "Git履歴 (最初/最新)",
            git_c.strftime("%Y-%m-%d %H:%M"),
            git_u.strftime("%Y-%m-%d %H:%M"),
        )
    table.add_row("OS統計情報 (作成)", os_c.strftime("%Y-%m-%d %H:%M"), "-")
    table.add_row("システム現在時刻", "-", now.strftime("%Y-%m-%d %H:%M"))
    console.print(table)

    # 3. 作成日時 (created_at) の選択
    c_mode = questionary.select(
        "作成日時 (created_at) をどうしますか？",
        choices=[
            questionary.Choice(
                f"現状維持 ({meta.get('created_at', {}).get('label', 'N/A')})",
                value="keep",
            ),
            questionary.Choice(
                f"Gitの最初のコミットに合わせる ({git_c.strftime('%Y-%m-%d') if git_c else 'N/A'})",
                value="git",
            ),
            questionary.Choice(
                f"OSの作成日時に合わせる ({os_c.strftime('%Y-%m-%d')})", value="os"
            ),
            questionary.Choice("手動入力する", value="manual"),
        ],
    ).ask()

    if c_mode == "git" and git_c:
        manager.data["metadata"]["created_at"] = format_meta(git_c)
    elif c_mode == "os":
        manager.data["metadata"]["created_at"] = format_meta(os_c)
    elif c_mode == "manual":
        val = questionary.text("New Created Label (YYYY-MM-DD HH:MM):").ask()
        manager.data["metadata"]["created_at"]["label"] = val
        manager.data["metadata"]["created_at"]["iso"] = (
            now.isoformat() + "Z"
        )  # ISOは操作時刻をベース

    # 4. 更新日時 (updated_at) の選択
    u_mode = questionary.select(
        "更新日時 (updated_at) をどうしますか？",
        choices=[
            questionary.Choice(
                f"手書き情報を維持 ({meta.get('updated_at', {}).get('label', 'N/A')})",
                value="keep",
            ),
            questionary.Choice(
                f"Gitの最新コミットに合わせる ({git_u.strftime('%m/%d %H:%M') if git_u else 'N/A'})",
                value="git",
            ),
            questionary.Choice(
                f"現在時刻にする ({now.strftime('%m/%d %H:%M')})", value="now"
            ),
            questionary.Choice("手動入力する", value="manual"),
        ],
    ).ask()

    if u_mode == "git" and git_u:
        manager.data["metadata"]["updated_at"] = format_meta(git_u)
    elif u_mode == "now":
        manager.data["metadata"]["updated_at"] = format_meta(now)
    elif u_mode == "manual":
        val = questionary.text("New Updated Label (YYYY-MM-DD HH:MM):").ask()
        manager.data["metadata"]["updated_at"]["label"] = val
        manager.data["metadata"]["updated_at"]["iso"] = now.isoformat() + "Z"

    # 5. 保存
    valid, msg = manager.validate_schema()
    if not valid:
        console.print(Panel(f"Schema Error: {msg}", border_style="bold red"))
        if not questionary.confirm("エラーを無視して保存しますか？").ask():
            return

    if manager.show_diff():
        if questionary.confirm("保存しますか？").ask():
            manager.save()
            console.print("[bold green]Success![/bold green]")


if __name__ == "__main__":
    main()
