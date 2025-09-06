from flask import Flask, render_template, request, redirect, session, url_for
from peewee import Model, CharField, SqliteDatabase
from werkzeug.security import generate_password_hash, check_password_hash

import os  # ← 追加
import csv  # ← 追加
import datetime  # ← 追加
from werkzeug.utils import secure_filename  # ← 追加


app = Flask(__name__)
app.secret_key = "your-secret-key"  # 本番では .env で管理

# SQLiteデータベースの設定
db = SqliteDatabase("users.db")


# ユーザーモデルの定義
class User(Model):
    name = CharField(unique=True)
    email = CharField()
    password_hash = CharField()
    role = CharField(default="reporter")  # reporter / editor / admin

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    class Meta:
        database = db


class Report(Model):
    reportno = CharField(unique=True)  # 報告番号
    user = CharField()  # ユーザー名（またはID）
    date = CharField()
    start_time = CharField()
    end_time = CharField()
    method = CharField()
    hunter = CharField()
    location = CharField()
    animal = CharField()
    sex = CharField()
    tasks = CharField()  # カンマ区切りで保存
    tail_submitted = CharField()  # "yes" or "no"

    class Meta:
        database = db


class Member(Model):
    name = CharField(unique=True)  # メンバー名
    # 大型獣用番号
    large_license_permit = CharField(null=True)  # 大型獣用許可番号
    large_license_operator = CharField(null=True)  # 大型獣用従事者番号
    large_license_instruction = CharField(null=True)  # 大型獣用指示書番号
    # 小型獣用番号
    small_license_permit = CharField(null=True)  # 小型獣用許可番号
    small_license_operator = CharField(null=True)  # 小型獣用従事者番号
    small_license_instruction = CharField(null=True)  # 小型獣用指示書番号
    phone = CharField(null=True)  # 電話番号
    email = CharField(null=True)  # メールアドレス
    address = CharField(null=True)  # 住所
    join_date = CharField(null=True)  # 入会日
    status = CharField(default="active")  # active / inactive
    notes = CharField(null=True)  # 備考

    class Meta:
        database = db


# DB初期化
db.connect()

# データベースの再作成（開発環境用）
# 本番環境では削除してください
RECREATE_DB = False  # データベースを再作成する場合はTrue or False

if RECREATE_DB:
    try:
        # 既存のテーブルを削除
        db.drop_tables([User, Report, Member], safe=True)
        print("既存のテーブルを削除しました")
    except Exception as e:
        print(f"テーブル削除エラー: {e}")

# テーブルを作成
db.create_tables([User, Report, Member])
print("テーブルを作成しました")

# マイグレーション処理（データベース再作成しない場合）
if not RECREATE_DB:
    try:
        # テーブルが存在するかチェック
        cursor = db.execute_sql("SELECT name FROM sqlite_master WHERE type='table' AND name='report'")
        if cursor.fetchone():
            # reportnoカラムが存在するかチェック
            cursor = db.execute_sql("PRAGMA table_info(report)")
            columns = [row[1] for row in cursor.fetchall()]
            if "reportno" not in columns:
                db.execute_sql("ALTER TABLE report ADD COLUMN reportno VARCHAR(255)")
                print("reportnoフィールドを追加しました")
            else:
                print("reportnoフィールドは既に存在します")
        else:
            print("reportテーブルが存在しません")
    except Exception as e:
        print(f"マイグレーションエラー: {e}")


# トップページのルーティング
@app.route("/")
def home():
    if User.select().count() == 0:
        return redirect("/register")  # 初回は登録画面へ
    if "user_id" in session:
        return redirect("/dashboard")
    return redirect("/login")


# ユーザー登録画面と処理
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form.get("role", "reporter")
        user = User(name=name, email=email, role=role)
        user.set_password(password)
        user.save()
        print(f"登録完了: {user.name}")
        return redirect(url_for("login", registered=1))
    return render_template("register.html")


# ログイン画面と処理
@app.route("/login", methods=["GET", "POST"])
def login():
    message = None
    if request.args.get("registered") == "1":
        message = "登録完了しました。ログインしてください。"

    if request.method == "POST":
        name = request.form["name"]
        password = request.form["password"]
        user = User.get_or_none(User.name == name)
        if user and user.check_password(password):
            session["user_id"] = user.id
            return redirect("/dashboard")
        else:
            message = "ログイン失敗：名前またはパスワードが正しくありません。"
    return render_template("login.html", message=message)


# ログイン後のダッシュボード
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")
    user = User.get_by_id(session["user_id"])
    return render_template("dashboard.html", user=user)


def load_csv_list(filename):
    base = os.path.dirname(__file__)
    path = os.path.join(base, filename)
    with open(path, encoding="utf-8") as f:
        return [row[0] for row in csv.reader(f) if row]


@app.route("/report/new", methods=["GET", "POST"])
def new_report():
    if "user_id" not in session:
        return redirect("/login")

    locations = load_csv_list("data/地名.csv")
    animals = load_csv_list("data/鳥獣.csv")
    sexs = ["オス", "メス", "不明"]
    tasks = load_csv_list("data/従事内容.csv")
    members = load_csv_list("data/猟友会名簿.csv")

    if request.method == "POST":
        try:
            # 報告番号を生成（日付+連番）
            today = datetime.date.today().strftime("%Y%m%d")
            # 今日の報告数を取得して連番を生成
            today_reports = Report.select().where(Report.reportno.like(f"{today}%")).count()
            reportno = f"{today}{today_reports + 1:03d}"

            # フォームデータを取得
            date = request.form["date"]
            start_time = request.form["start_time"]
            end_time = request.form["end_time"]
            method = request.form["method"]
            hunter = request.form["hunter"]
            location = request.form["location"]
            animal = request.form["animal"]
            sex = request.form["sex"]
            tasks = ",".join(request.form.getlist("tasks"))  # チェックボックスの値をカンマ区切りで結合
            tail_submitted = "yes" if request.form.get("tail_submitted") else "no"

            # ユーザー情報を取得
            user = User.get_by_id(session["user_id"])

            # データベースに保存
            report = Report(
                reportno=reportno,
                user=user.name,
                date=date,
                start_time=start_time,
                end_time=end_time,
                method=method,
                hunter=hunter,
                location=location,
                animal=animal,
                sex=sex,
                tasks=tasks,
                tail_submitted=tail_submitted,
            )
            report.save()

            # 写真のアップロード処理
            photos = request.files.getlist("photos")
            if photos and photos[0].filename:  # 写真がアップロードされている場合
                upload_dir = os.path.join(os.path.dirname(__file__), "uploads", reportno)
                os.makedirs(upload_dir, exist_ok=True)

                for i, photo in enumerate(photos):
                    if photo.filename:
                        filename = secure_filename(photo.filename)
                        # ファイル名に番号を付けて保存
                        name, ext = os.path.splitext(filename)
                        new_filename = f"{i+1:02d}_{name}{ext}"
                        photo.save(os.path.join(upload_dir, new_filename))

            return f"報告を受け付けました！報告番号: {reportno}"

        except Exception as e:
            return f"エラーが発生しました: {str(e)}"

    return render_template(
        "report_form.html", members=members, locations=locations, animals=animals, tasks=tasks, sexs=sexs
    )


# 報告一覧表示
@app.route("/reports")
def reports():
    if "user_id" not in session:
        return redirect("/login")

    user = User.get_by_id(session["user_id"])
    # 管理者の場合は全報告を表示、それ以外は自分の報告のみ
    if user.role == "admin":
        reports_list = Report.select().order_by(Report.reportno.desc())
    else:
        reports_list = Report.select().where(Report.user == user.name).order_by(Report.reportno.desc())

    return render_template("reports.html", reports=reports_list, user=user)


# 猟友会メンバー管理
@app.route("/members/manage")
def manage_members():
    if "user_id" not in session:
        return redirect("/login")

    user = User.get_by_id(session["user_id"])
    if user.role not in ["editor", "admin"]:
        return "アクセス権限がありません", 403

    members = Member.select().order_by(Member.name)
    return render_template("manage_members.html", members=members, user=user)


# メンバー追加
@app.route("/members/add", methods=["GET", "POST"])
def add_member():
    if "user_id" not in session:
        return redirect("/login")

    user = User.get_by_id(session["user_id"])
    if user.role not in ["editor", "admin"]:
        return "アクセス権限がありません", 403

    if request.method == "POST":
        try:
            member = Member(
                name=request.form["name"],
                large_license_permit=request.form.get("large_license_permit", ""),
                large_license_operator=request.form.get("large_license_operator", ""),
                large_license_instruction=request.form.get("large_license_instruction", ""),
                small_license_permit=request.form.get("small_license_permit", ""),
                small_license_operator=request.form.get("small_license_operator", ""),
                small_license_instruction=request.form.get("small_license_instruction", ""),
                phone=request.form.get("phone", ""),
                email=request.form.get("email", ""),
                address=request.form.get("address", ""),
                join_date=request.form.get("join_date", ""),
                status=request.form.get("status", "active"),
                notes=request.form.get("notes", ""),
            )
            member.save()
            return redirect("/members/manage")
        except Exception as e:
            return f"エラーが発生しました: {str(e)}"

    return render_template("add_member.html", user=user)


# メンバー編集
@app.route("/members/edit/<int:member_id>", methods=["GET", "POST"])
def edit_member(member_id):
    if "user_id" not in session:
        return redirect("/login")

    user = User.get_by_id(session["user_id"])
    if user.role not in ["editor", "admin"]:
        return "アクセス権限がありません", 403

    try:
        member = Member.get_by_id(member_id)
    except Member.DoesNotExist:
        return "メンバーが見つかりません", 404

    if request.method == "POST":
        try:
            member.name = request.form["name"]
            member.large_license_permit = request.form.get("large_license_permit", "")
            member.large_license_operator = request.form.get("large_license_operator", "")
            member.large_license_instruction = request.form.get("large_license_instruction", "")
            member.small_license_permit = request.form.get("small_license_permit", "")
            member.small_license_operator = request.form.get("small_license_operator", "")
            member.small_license_instruction = request.form.get("small_license_instruction", "")
            member.phone = request.form.get("phone", "")
            member.email = request.form.get("email", "")
            member.address = request.form.get("address", "")
            member.join_date = request.form.get("join_date", "")
            member.status = request.form.get("status", "active")
            member.notes = request.form.get("notes", "")
            member.save()
            return redirect("/members/manage")
        except Exception as e:
            return f"エラーが発生しました: {str(e)}"

    return render_template("edit_member.html", member=member, user=user)


# メンバー削除
@app.route("/members/delete/<int:member_id>", methods=["POST"])
def delete_member(member_id):
    if "user_id" not in session:
        return redirect("/login")

    user = User.get_by_id(session["user_id"])
    if user.role not in ["editor", "admin"]:
        return "アクセス権限がありません", 403

    try:
        member = Member.get_by_id(member_id)
        member.delete_instance()
        return redirect("/members/manage")
    except Member.DoesNotExist:
        return "メンバーが見つかりません", 404
    except Exception as e:
        return f"エラーが発生しました: {str(e)}"


# CSVインポート
@app.route("/members/import_csv", methods=["GET", "POST"])
def import_csv():
    if "user_id" not in session:
        return redirect("/login")

    user = User.get_by_id(session["user_id"])
    if user.role not in ["editor", "admin"]:
        return "アクセス権限がありません", 403

    if request.method == "POST":
        try:
            import csv
            import os

            csv_file_path = "data/猟友会名簿.csv"
            if not os.path.exists(csv_file_path):
                return "CSVファイルが見つかりません", 404

            imported_count = 0
            skipped_count = 0

            with open(csv_file_path, "r", encoding="utf-8") as file:
                csv_reader = csv.reader(file)
                for row in csv_reader:
                    if row and row[0].strip():  # 空行でない場合
                        name = row[0].strip()
                        try:
                            # 既存のメンバーかチェック
                            existing_member = Member.get(Member.name == name)
                            skipped_count += 1
                        except Member.DoesNotExist:
                            # 新しいメンバーを作成
                            member = Member(name=name, status="active")
                            member.save()
                            imported_count += 1

            return f"インポート完了: {imported_count}件追加, {skipped_count}件スキップ"

        except Exception as e:
            return f"エラーが発生しました: {str(e)}"

    return render_template("import_csv.html", user=user)


# ログアウト処理
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True)
