from flask import Flask, render_template, request, redirect, session, url_for, send_from_directory
from peewee import Model, CharField, SqliteDatabase
from werkzeug.security import generate_password_hash, check_password_hash

# メール機能を無効化する場合は以下の行をコメントアウト
try:
    from flask_mail import Mail, Message

    MAIL_AVAILABLE = True
except ImportError:
    MAIL_AVAILABLE = False
    print("Flask-Mailが利用できません。メール機能は無効化されます。")

import os  # ← 追加
import csv  # ← 追加
import datetime  # ← 追加
from werkzeug.utils import secure_filename  # ← 追加


app = Flask(__name__)
app.secret_key = "your-secret-key"  # 本番では .env で管理

# メール設定
app.config["MAIL_SERVER"] = "smtp.gmail.com"  # Gmailを使用する場合
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "your-email@gmail.com"  # 送信者メールアドレス
app.config["MAIL_PASSWORD"] = "your-app-password"  # アプリパスワード
app.config["MAIL_DEFAULT_SENDER"] = "your-email@gmail.com"

# 役場担当者のメールアドレス
YAKUBA_EMAIL = "tttsss120604280520@example.com"  # 実際の役場メールアドレスに変更

# メール機能の初期化
if MAIL_AVAILABLE:
    mail = Mail(app)
else:
    mail = None

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
    team_members = CharField(null=True)  # 実施隊従事者（カンマ区切りで保存）
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
    birthday_date = CharField(null=True)  # 誕生日
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
            # カラムが存在するかチェック
            cursor = db.execute_sql("PRAGMA table_info(report)")
            columns = [row[1] for row in cursor.fetchall()]

            if "reportno" not in columns:
                db.execute_sql("ALTER TABLE report ADD COLUMN reportno VARCHAR(255)")
                print("reportnoフィールドを追加しました")
            else:
                print("reportnoフィールドは既に存在します")

            if "team_members" not in columns:
                db.execute_sql("ALTER TABLE report ADD COLUMN team_members VARCHAR(255)")
                print("team_membersフィールドを追加しました")
            else:
                print("team_membersフィールドは既に存在します")
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


def send_report_notification_email(report, user):
    """役場担当者に報告通知メールを送信"""
    try:
        # 現在の日時を取得
        now = datetime.datetime.now()
        report_date = now.strftime("%Y年%m月%d日 %H:%M")
        current_time = now.strftime("%Y年%m月%d日 %H:%M:%S")

        # メール件名
        subject = f"【猟友会報告】大型・小型有害鳥獣捕獲活動報告 - {report.reportno}"

        # メール本文をHTMLテンプレートから生成
        html_body = render_template(
            "email_report_notification.html",
            report=report,
            user=user,
            report_date=report_date,
            current_time=current_time,
        )

        # メールメッセージを作成
        msg = Message(subject=subject, recipients=[YAKUBA_EMAIL], html=html_body)

        # メール送信
        mail.send(msg)
        print(f"報告通知メールを送信しました: {report.reportno}")

    except Exception as e:
        print(f"メール送信でエラーが発生しました: {e}")
        raise


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
            # 報告番号を生成（日付+連番）- 重複回避機能付き
            today = datetime.date.today().strftime("%Y%m%d")
            reportno = None
            for attempt in range(10):  # 最大10回試行
                # 今日の最大報告番号を取得して連番を生成
                max_report = (
                    Report.select()
                    .where(Report.reportno.like(f"{today}%"))
                    .order_by(Report.reportno.desc())
                    .first()
                )
                if max_report:
                    # 既存の最大番号から次の番号を生成
                    last_number = int(max_report.reportno[-3:])  # 最後の3桁を取得
                    next_number = last_number + 1 + attempt  # 試行回数を加算
                else:
                    # 今日初めての報告
                    next_number = 1 + attempt

                candidate_reportno = f"{today}{next_number:03d}"

                # 重複チェック
                existing = Report.get_or_none(Report.reportno == candidate_reportno)
                if not existing:
                    reportno = candidate_reportno
                    break

            if not reportno:
                return "報告番号の生成に失敗しました。しばらく時間をおいてから再試行してください。"

            # フォームデータを取得
            date = request.form["date"]
            start_time = request.form["start_time"]
            end_time = request.form["end_time"]
            method = request.form["method"]
            hunter = request.form["hunter"]
            team_members = ",".join(request.form.getlist("team_members"))  # 実施隊従事者をカンマ区切りで結合
            location = request.form["location"]
            animal = request.form["animal"]
            sex = request.form["sex"]
            tasks = ",".join(request.form.getlist("tasks"))  # チェックボックスの値をカンマ区切りで結合
            tail_submitted = "yes" if request.form.get("tail_submitted") else "no"

            # フォームデータをセッションに保存（エラー時の復元用）
            session["form_data"] = {
                "date": request.form["date"],
                "start_time": request.form["start_time"],
                "end_time": request.form["end_time"],
                "method": request.form["method"],
                "hunter": request.form["hunter"],
                "team_members": request.form.getlist("team_members"),
                "location": request.form["location"],
                "animal": request.form["animal"],
                "sex": request.form["sex"],
                "tasks": request.form.getlist("tasks"),
                "tail_submitted": request.form.get("tail_submitted"),
            }

            # 写真のバリデーション（2枚以上必須）
            photos = request.files.getlist("photos")
            valid_photos = [photo for photo in photos if photo.filename]
            if len(valid_photos) < 2:
                return render_template(
                    "error.html",
                    error_message=f"写真は2枚以上必要です。現在の枚数: {len(valid_photos)}",
                    back_url="/report/new",
                )

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
                team_members=team_members,
                location=location,
                animal=animal,
                sex=sex,
                tasks=tasks,
                tail_submitted=tail_submitted,
            )
            report.save()

            # 写真のアップロード処理
            if valid_photos:  # バリデーション済みの写真をアップロード
                upload_dir = os.path.join(os.path.dirname(__file__), "uploads", reportno)
                os.makedirs(upload_dir, exist_ok=True)

                for i, photo in enumerate(valid_photos):
                    filename = secure_filename(photo.filename)
                    # ファイル名に番号を付けて保存
                    name, ext = os.path.splitext(filename)
                    new_filename = f"{i+1:02d}_{name}{ext}"
                    photo.save(os.path.join(upload_dir, new_filename))

            # 役場担当者にメール通知を送信（メール機能が利用可能で設定が完了している場合のみ）
            if MAIL_AVAILABLE and app.config["MAIL_USERNAME"] != "your-email@gmail.com":
                try:
                    send_report_notification_email(report, user)
                except Exception as e:
                    print(f"メール送信エラー: {e}")
                    # メール送信に失敗しても報告は成功とする
            else:
                if not MAIL_AVAILABLE:
                    print("Flask-Mailが利用できないため、メール送信をスキップしました")
                else:
                    print("メール設定が未完了のため、メール送信をスキップしました")

            # 成功時にセッションデータをクリア
            session.pop("form_data", None)
            return render_template("report_success.html", reportno=reportno)

        except Exception as e:
            return f"エラーが発生しました: {str(e)}"

    # セッションからフォームデータを復元
    form_data = session.get("form_data", {})

    return render_template(
        "report_form.html",
        members=members,
        locations=locations,
        animals=animals,
        tasks=tasks,
        sexs=sexs,
        form_data=form_data,
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


# 報告書印刷
@app.route("/report/print/<report_id>")
def print_report(report_id):
    if "user_id" not in session:
        return redirect("/login")

    try:
        # 報告データを取得
        report = Report.get_by_id(report_id)

        # 猟友会メンバー情報を取得
        member = Member.get_or_none(Member.name == report.hunter)
        if not member:
            # メンバーが見つからない場合は空のオブジェクトを作成
            class EmptyMember:
                large_license_permit = None
                large_license_operator = None
                large_license_instruction = None
                small_license_permit = None
                small_license_operator = None
                small_license_instruction = None

            member = EmptyMember()

        # 写真ファイルを取得
        photos = []
        upload_dir = os.path.join(os.path.dirname(__file__), "uploads", report.reportno)
        if os.path.exists(upload_dir):
            photo_files = [
                f for f in os.listdir(upload_dir) if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif"))
            ]
            photo_files.sort()  # ファイル名順にソート
            for photo_file in photo_files:
                photos.append(f"/uploads/{report.reportno}/{photo_file}")

        # 今日の日付を取得
        today = datetime.date.today().strftime("%Y年%m月%d日")

        return render_template("report_print.html", report=report, member=member, photos=photos, today=today)

    except Report.DoesNotExist:
        return "報告が見つかりません", 404
    except Exception as e:
        return f"エラーが発生しました: {str(e)}", 500


# 写真ファイルの静的配信
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
    return send_from_directory(uploads_dir, filename)


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
                birthday_date=request.form.get("birthday_date", ""),
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
            member.birthday_date = request.form.get("birthday_date", "")
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
