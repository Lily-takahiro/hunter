from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    url_for,
    send_from_directory,
    make_response,
)
from peewee import Model, CharField, BooleanField, SqliteDatabase
from werkzeug.security import generate_password_hash, check_password_hash

# 環境変数とスケジューラーの安全な読み込み
try:
    from dotenv import load_dotenv

    load_dotenv(override=True)
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("python-dotenvが利用できません。環境変数は手動で設定してください。")

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False
    print("APSchedulerが利用できません。写真自動削除機能は無効化されます。")
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
app.config["MAIL_USERNAME"] = "tttsss120604280520@gmail.com"  # 送信者メールアドレス
app.config["MAIL_PASSWORD"] = os.environ.get("PWD")  # アプリパスワードy
app.config["MAIL_DEFAULT_SENDER"] = "tttsss120604280520@gmail.com"

# 役場担当者のメールアドレス
YAKUBA_EMAIL = "tttsss120604280520@gmail.com"  # 実際の役場メールアドレスに変更

# メール送信者設定
# "fixed": 固定の送信者アドレスを使用
# "user": ログインユーザーのメールアドレスを使用
MAIL_SENDER_MODE = "user"  # "fixed" または "user"

# 写真削除設定
PHOTO_CLEANUP_DAYS = 60  # 削除対象の日数
PHOTO_CLEANUP_ENABLED = True  # 自動削除機能の有効/無効

# メール機能の初期化
if MAIL_AVAILABLE:
    mail = Mail(app)
else:
    mail = None

# スケジューラーの安全な初期化
if SCHEDULER_AVAILABLE:
    scheduler = BackgroundScheduler()
else:
    scheduler = None


def scheduled_photo_cleanup():
    """定期実行される写真削除処理"""
    if PHOTO_CLEANUP_ENABLED:
        print("定期写真削除処理を開始します...")
        result = cleanup_old_photos(PHOTO_CLEANUP_DAYS)
        if result:
            print(f"定期削除完了: {result['deleted_count']}件の写真を削除しました")
        else:
            print("定期削除処理でエラーが発生しました")
    else:
        print("写真自動削除機能が無効になっています")


# 毎日午前2時に写真削除処理を実行（安全な初期化）
if PHOTO_CLEANUP_ENABLED and SCHEDULER_AVAILABLE and scheduler is not None:
    try:
        scheduler.add_job(
            func=scheduled_photo_cleanup,
            trigger=CronTrigger(hour=2, minute=0),  # 毎日午前2時
            id="photo_cleanup",
            name="写真削除処理",
            replace_existing=True,
        )
        scheduler.start()
        print("写真自動削除スケジューラーを開始しました (毎日午前2時実行)")
    except Exception as e:
        print(f"スケジューラー起動エラー: {e}")
        print("写真自動削除機能を無効化します")
        PHOTO_CLEANUP_ENABLED = False
elif not SCHEDULER_AVAILABLE:
    print("APSchedulerが利用できないため、写真自動削除機能を無効化します")
    PHOTO_CLEANUP_ENABLED = False

# SQLiteデータベースの設定
db = SqliteDatabase("users.db")


# ユーザーモデルの定義
class User(Model):
    name = CharField(unique=True)
    email = CharField()
    password_hash = CharField()
    role = CharField(default="reporter")  # reporter / editor / admin
    created_at = CharField(null=True)  # 作成日時

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
    email_sent = BooleanField(default=False)  # メール送信済みフラグ
    email_sent_date = CharField(null=True)  # メール送信日時
    email_sent_by = CharField(null=True)  # メール送信者
    photo_upload_date = CharField(null=True)  # 写真アップロード日時

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

            if "email_sent" not in columns:
                db.execute_sql("ALTER TABLE report ADD COLUMN email_sent BOOLEAN DEFAULT 0")
                print("email_sentフィールドを追加しました")
            else:
                print("email_sentフィールドは既に存在します")

            if "email_sent_date" not in columns:
                db.execute_sql("ALTER TABLE report ADD COLUMN email_sent_date VARCHAR(255)")
                print("email_sent_dateフィールドを追加しました")
            else:
                print("email_sent_dateフィールドは既に存在します")

            if "email_sent_by" not in columns:
                db.execute_sql("ALTER TABLE report ADD COLUMN email_sent_by VARCHAR(255)")
                print("email_sent_byフィールドを追加しました")
            else:
                print("email_sent_byフィールドは既に存在します")

            if "photo_upload_date" not in columns:
                db.execute_sql("ALTER TABLE report ADD COLUMN photo_upload_date VARCHAR(255)")
                print("photo_upload_dateフィールドを追加しました")
            else:
                print("photo_upload_dateフィールドは既に存在します")
        else:
            print("reportテーブルが存在しません")
    except Exception as e:
        print(f"Reportテーブルマイグレーションエラー: {e}")

    # Userテーブルのマイグレーション
    try:
        if db.table_exists("user"):
            columns = [column.name for column in db.get_columns("user")]

            if "created_at" not in columns:
                db.execute_sql("ALTER TABLE user ADD COLUMN created_at VARCHAR(255)")
                print("userテーブルにcreated_atフィールドを追加しました")
            else:
                print("userテーブルのcreated_atフィールドは既に存在します")
        else:
            print("userテーブルが存在しません")
    except Exception as e:
        print(f"Userテーブルマイグレーションエラー: {e}")


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
        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user = User(name=name, email=email, role=role, created_at=created_at)
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
    current_time = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M")
    return render_template("dashboard.html", user=user, current_time=current_time)


def load_csv_list(filename):
    base = os.path.dirname(__file__)
    path = os.path.join(base, filename)
    with open(path, encoding="utf-8") as f:
        return [row[0] for row in csv.reader(f) if row]


def get_mail_sender(user):
    """メール送信者アドレスを取得"""
    if MAIL_SENDER_MODE == "user" and user.email:
        return (user.name, user.email)
    else:
        return app.config["MAIL_DEFAULT_SENDER"]


def cleanup_old_photos(days=60):
    """指定日数経過した写真を削除する関数"""
    try:
        from datetime import datetime, timedelta

        # 削除対象の日付を計算
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_date_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")

        print(f"写真削除処理開始: {days}日以上前の写真を削除します (基準日: {cutoff_date_str})")

        # 削除対象の報告を取得
        old_reports = Report.select().where(
            (Report.photo_upload_date.is_null(False)) & (Report.photo_upload_date < cutoff_date_str)
        )

        deleted_count = 0
        deleted_size = 0
        deleted_reports = []

        for report in old_reports:
            try:
                # 写真ディレクトリのパス
                upload_dir = os.path.join(os.path.dirname(__file__), "uploads", report.reportno)

                if os.path.exists(upload_dir):
                    # ディレクトリ内のファイルサイズを計算
                    dir_size = 0
                    for root, dirs, files in os.walk(upload_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            dir_size += os.path.getsize(file_path)

                    # ディレクトリを削除
                    import shutil

                    shutil.rmtree(upload_dir)

                    deleted_count += 1
                    deleted_size += dir_size
                    deleted_reports.append(
                        {
                            "reportno": report.reportno,
                            "upload_date": report.photo_upload_date,
                            "size": dir_size,
                        }
                    )

                    print(
                        f"削除完了: {report.reportno} (アップロード日: {report.photo_upload_date}, サイズ: {dir_size} bytes)"
                    )

                # データベースからphoto_upload_dateをクリア（報告自体は残す）
                report.photo_upload_date = None
                report.save()

            except Exception as e:
                print(f"写真削除エラー ({report.reportno}): {e}")
                continue

        # 削除結果をログに記録
        result = {
            "deleted_count": deleted_count,
            "deleted_size": deleted_size,
            "deleted_reports": deleted_reports,
            "cutoff_date": cutoff_date_str,
        }

        print(
            f"写真削除処理完了: {deleted_count}件の報告の写真を削除しました (総サイズ: {deleted_size} bytes)"
        )
        return result

    except Exception as e:
        print(f"写真削除処理でエラーが発生しました: {e}")
        return None


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

        # メールメッセージを作成（送信者を動的に設定）
        msg = Message(
            subject=subject,
            recipients=[YAKUBA_EMAIL],
            html=html_body,
            sender=get_mail_sender(user),  # 送信者アドレスを動的に取得
            charset="utf-8",
        )

        # メール送信
        mail.send(msg)
        print(f"報告通知メールを送信しました: {report.reportno}")

    except Exception as e:
        print(f"メール送信でエラーが発生しました: {e}")
        raise


@app.route("/report/new", methods=["GET", "POST"])
def new_report():
    print(f"new_report() が呼び出されました - メソッド: {request.method}")

    if "user_id" not in session:
        print("セッションにuser_idがありません - ログインページにリダイレクト")
        return redirect("/login")

    locations = load_csv_list("data/地名.csv")
    animals = load_csv_list("data/鳥獣.csv")
    sexs = ["オス", "メス", "不明"]
    tasks = load_csv_list("data/従事内容.csv")
    members = load_csv_list("data/猟友会名簿.csv")

    print(f"CSVデータ読み込み完了 - メンバー数: {len(members)}")

    if request.method == "POST":
        user = User.get_by_id(session["user_id"])
        print(f"新規報告フォーム送信開始 - ユーザー: {user.name}")
        print(f"アップロードファイル数: {len(request.files.getlist('photos'))}")
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

            # 写真のバリデーション（1枚以上必須）
            photos = request.files.getlist("photos")
            valid_photos = [photo for photo in photos if photo.filename]
            print(f"アップロードされた写真数: {len(photos)}, 有効な写真数: {len(valid_photos)}")

            if len(valid_photos) < 1:
                return render_template(
                    "error.html",
                    error_message=f"写真は1枚以上必要です。現在の枚数: {len(valid_photos)}",
                    back_url="/report/new",
                )

            # ユーザー情報を取得
            user = User.get_by_id(session["user_id"])

            # 現在の日時を取得
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
                photo_upload_date=current_time,  # 写真アップロード日時を記録
            )
            report.save()

            # 写真のアップロード処理
            if valid_photos:  # バリデーション済みの写真をアップロード
                upload_dir = os.path.join(os.path.dirname(__file__), "uploads", reportno)
                os.makedirs(upload_dir, exist_ok=True)
                print(f"アップロードディレクトリ: {upload_dir}")

                for i, photo in enumerate(valid_photos):
                    filename = secure_filename(photo.filename)
                    # ファイル名に番号を付けて保存
                    name, ext = os.path.splitext(filename)
                    new_filename = f"{i+1:02d}_{name}{ext}"
                    file_path = os.path.join(upload_dir, new_filename)
                    photo.save(file_path)
                    print(f"写真を保存しました: {file_path}")

            # 役場担当者にメール通知を送信（メール機能が利用可能で設定が完了している場合のみ）
            if (
                MAIL_AVAILABLE
                and app.config["MAIL_USERNAME"]
                and app.config["MAIL_USERNAME"] != "your-email@gmail.com"
            ):
                try:
                    send_report_notification_email(report, user)
                    print("役場担当者へのメール通知を送信しました")
                except Exception as e:
                    print(f"メール送信エラー: {e}")
                    # メール送信に失敗しても報告は成功とする
            else:
                if not MAIL_AVAILABLE:
                    print("Flask-Mailが利用できないため、メール送信をスキップしました")
                elif not app.config["MAIL_USERNAME"]:
                    print("メールユーザー名が設定されていないため、メール送信をスキップしました")
                else:
                    print("メール設定が未完了のため、メール送信をスキップしました")

            # 成功時にセッションデータをクリア
            session.pop("form_data", None)
            print(f"報告が正常に作成されました: {reportno}")

            # メール送信状況を確認
            mail_sent = False
            if (
                MAIL_AVAILABLE
                and app.config["MAIL_USERNAME"]
                and app.config["MAIL_USERNAME"] != "your-email@gmail.com"
            ):
                mail_sent = True

            return render_template("report_success.html", reportno=reportno, mail_sent=mail_sent)

        except Exception as e:
            print(f"報告作成エラー: {str(e)}")
            import traceback

            traceback.print_exc()
            return render_template(
                "error.html",
                error_message=f"報告の作成中にエラーが発生しました: {str(e)}",
                back_url="/report/new",
            )

    # セッションからフォームデータを復元
    form_data = session.get("form_data", {})
    print(f"GET処理 - フォームデータ: {form_data}")

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


# メール返信フォーム表示
@app.route("/reports/<int:report_id>/email")
def email_reply_form(report_id):
    if "user_id" not in session:
        return redirect("/login")

    user = User.get_by_id(session["user_id"])
    if user.role != "admin":
        return "アクセス権限がありません", 403

    try:
        report = Report.get_by_id(report_id)

        # メールテンプレート
        email_template = f"""{report.user} 様

この度は、猟友会活動報告書をご提出いただき、誠にありがとうございます。

以下の報告書を受理いたしました：

■ 報告番号: {report.reportno}
■ 実施日: {report.date}
■ 捕獲鳥獣: {report.animal}
■ 捕獲場所: {report.location}

報告書の内容を確認させていただき、適切に処理いたします。
今後とも猟友会活動にご協力のほど、よろしくお願いいたします。

---
{user.name}
役場担当者"""

        return render_template(
            "email_reply.html", report=report, current_user=user, email_template=email_template
        )
    except Report.DoesNotExist:
        return "報告が見つかりません", 404


# メール送信処理
@app.route("/reports/<int:report_id>/email", methods=["POST"])
def send_email_reply(report_id):
    if "user_id" not in session:
        return redirect("/login")

    user = User.get_by_id(session["user_id"])
    if user.role != "admin":
        return "アクセス権限がありません", 403

    try:
        report = Report.get_by_id(report_id)

        # 既にメール送信済みかチェック
        if report.email_sent:
            return render_template(
                "error.html",
                error_message="この報告には既にメールが送信されています。",
                back_url=f"/reports/{report_id}/email",
            )

        subject = request.form.get("subject")
        body = request.form.get("body")
        send_copy = request.form.get("send_copy") == "on"

        if not MAIL_AVAILABLE:
            return render_template(
                "error.html",
                error_message="メール機能が利用できません。システム管理者にお問い合わせください。",
                back_url=f"/reports/{report_id}/email",
            )

        # 報告者の実際のメールアドレスを取得
        print(f"報告データ: report.user = {report.user}")

        # デバッグ: 全ユーザー情報を表示
        all_users = User.select()
        print("データベース内の全ユーザー:")
        for u in all_users:
            print(f"  - 名前: {u.name}, メール: {u.email}")

        try:
            report_user = User.get(User.name == report.user)
            recipient_email = report_user.email
            print(f"報告者のメールアドレスを取得: {report.user} -> {recipient_email}")
        except User.DoesNotExist:
            # ユーザーが見つからない場合はデフォルトのメールアドレスを使用
            recipient_email = f"{report.user}@gmail.com"
            print(f"ユーザーが見つからないためデフォルトメールを使用: {recipient_email}")

        msg = Message(
            subject=subject,
            recipients=[recipient_email],
            body=body,
            sender=get_mail_sender(user),  # 送信者アドレスを動的に取得
            charset="utf-8",
        )
        # メール送信
        try:
            # 報告者へのメール（送信者を動的に設定）
            print(f"メール送信先: {recipient_email}")
            msg = Message(
                subject=subject,
                recipients=[recipient_email],  # 上で取得した実際のメールアドレスを使用
                body=body,
                sender=get_mail_sender(user),  # 送信者アドレスを動的に取得
                charset="utf-8",
            )
            mail.send(msg)
            print(f"メール送信完了: {recipient_email}")

            # 役場担当者へのコピー（送信者を動的に設定）
            if send_copy:
                copy_msg = Message(
                    subject=f"[コピー] {subject}",
                    recipients=[YAKUBA_EMAIL],
                    body=f"以下のメールを送信しました：\n\n{body}",
                    sender=get_mail_sender(user),  # 送信者アドレスを動的に取得
                    charset="utf-8",
                )
                mail.send(copy_msg)

            # 送信状況を記録
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            report.email_sent = True
            report.email_sent_date = current_time
            report.email_sent_by = user.name
            report.save()

            return render_template(
                "email_success.html", report=report, message="メールを正常に送信しました。"
            )

        except Exception as e:
            return render_template(
                "error.html",
                error_message=f"メール送信に失敗しました: {str(e)}",
                back_url=f"/reports/{report_id}/email",
            )

    except Report.DoesNotExist:
        return "報告が見つかりません", 404


# ユーザー管理画面
@app.route("/users/manage")
def user_management():
    if "user_id" not in session:
        return redirect("/login")

    user = User.get_by_id(session["user_id"])
    if user.role != "admin":
        return "アクセス権限がありません", 403

    # 全ユーザーを取得（報告数も含める）
    users = []
    for u in User.select():
        report_count = Report.select().where(Report.user == u.name).count()
        users.append(
            {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "role": u.role,
                "created_at": u.created_at,
                "report_count": report_count,
            }
        )

    # 統計情報
    total_users = len(users)
    admin_count = len([u for u in users if u["role"] == "admin"])
    editor_count = len([u for u in users if u["role"] == "editor"])
    user_count = len([u for u in users if u["role"] == "user"])

    return render_template(
        "user_management.html",
        users=users,
        current_user=user,
        total_users=total_users,
        admin_count=admin_count,
        editor_count=editor_count,
        user_count=user_count,
    )


# ユーザー削除
@app.route("/users/<int:user_id>/delete", methods=["POST"])
def delete_user(user_id):
    if "user_id" not in session:
        return redirect("/login")

    current_user = User.get_by_id(session["user_id"])
    if current_user.role != "admin":
        return "アクセス権限がありません", 403

    try:
        # 削除対象のユーザーを取得
        target_user = User.get_by_id(user_id)

        # 自分自身は削除できない
        if target_user.id == current_user.id:
            return render_template(
                "error.html", error_message="自分自身を削除することはできません。", back_url="/users/manage"
            )

        # ユーザーに関連する報告データも削除
        Report.delete().where(Report.user == target_user.name).execute()

        # ユーザーを削除
        target_user.delete_instance()

        print(f"ユーザー '{target_user.name}' を削除しました")
        return redirect("/users/manage")

    except User.DoesNotExist:
        return render_template(
            "error.html", error_message="指定されたユーザーが見つかりません。", back_url="/users/manage"
        )
    except Exception as e:
        print(f"ユーザー削除エラー: {str(e)}")
        return render_template(
            "error.html",
            error_message=f"ユーザーの削除中にエラーが発生しました: {str(e)}",
            back_url="/users/manage",
        )


# CSV出力フォーム表示
@app.route("/reports/export")
def csv_export_form():
    if "user_id" not in session:
        return redirect("/login")

    user = User.get_by_id(session["user_id"])
    if user.role != "admin":
        return "アクセス権限がありません", 403

    # 統計情報を取得
    total_reports = Report.select().count()
    this_month = datetime.date.today().replace(day=1)
    this_month_reports = Report.select().where(Report.date >= this_month.strftime("%Y-%m-%d")).count()
    unique_hunters = Report.select(Report.user).distinct().count()

    return render_template(
        "csv_export.html",
        total_reports=total_reports,
        this_month_reports=this_month_reports,
        unique_hunters=unique_hunters,
    )


# CSV出力処理
@app.route("/reports/export", methods=["POST"])
def export_reports_csv():
    if "user_id" not in session:
        return redirect("/login")

    user = User.get_by_id(session["user_id"])
    if user.role != "admin":
        return "アクセス権限がありません", 403

    try:
        # フォームデータを取得
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        include_photos = request.form.get("include_photos") == "on"
        include_member_info = request.form.get("include_member_info") == "on"

        # 日付範囲で報告データを取得
        if start_date and end_date:
            reports = (
                Report.select()
                .where((Report.date >= start_date) & (Report.date <= end_date))
                .order_by(Report.reportno.desc())
            )
        else:
            reports = Report.select().order_by(Report.reportno.desc())

        # CSVヘッダーを生成
        headers = [
            "報告番号",
            "報告者",
            "実施日",
            "開始時間",
            "終了時間",
            "捕獲方法",
            "捕獲者",
            "実施隊従事者",
            "捕獲場所",
            "捕獲鳥獣",
            "性別",
            "従事内容",
            "しっぽ提出",
        ]

        # オプション項目を追加
        if include_member_info:
            headers.extend(
                [
                    "大型獣許可番号",
                    "大型獣従事者番号",
                    "大型獣指示書番号",
                    "小型獣許可番号",
                    "小型獣従事者番号",
                    "小型獣指示書番号",
                ]
            )

        if include_photos:
            headers.append("写真ファイル数")

        output = [headers]

        # データ行を生成
        for report in reports:
            row = [
                report.reportno,
                report.user,
                report.date,
                report.start_time,
                report.end_time,
                report.method,
                report.hunter,
                report.team_members or "",
                report.location,
                report.animal,
                report.sex,
                report.tasks or "",
                "提出済み" if report.tail_submitted == "yes" else "未提出",
            ]

            # 猟友会メンバー情報を追加
            if include_member_info:
                member = Member.get_or_none(Member.name == report.hunter)
                if member:
                    row.extend(
                        [
                            member.large_license_permit or "",
                            member.large_license_operator or "",
                            member.large_license_instruction or "",
                            member.small_license_permit or "",
                            member.small_license_operator or "",
                            member.small_license_instruction or "",
                        ]
                    )
                else:
                    row.extend(["", "", "", "", "", ""])

            # 写真情報を追加
            if include_photos:
                upload_dir = os.path.join(os.path.dirname(__file__), "uploads", report.reportno)
                photo_count = 0
                if os.path.exists(upload_dir):
                    photo_files = [
                        f
                        for f in os.listdir(upload_dir)
                        if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif"))
                    ]
                    photo_count = len(photo_files)
                row.append(str(photo_count))

            output.append(row)

        # CSVレスポンスを作成
        import io
        import csv

        # BOM付きUTF-8で出力（Excel対応）
        output_buffer = io.BytesIO()
        output_buffer.write("\ufeff".encode("utf-8"))  # BOMを追加

        # UTF-8でテキストを書き込み
        text_buffer = io.StringIO()
        writer = csv.writer(text_buffer)
        writer.writerows(output)

        # テキストをUTF-8バイトに変換して追加
        output_buffer.write(text_buffer.getvalue().encode("utf-8"))

        # ファイル名を生成
        if start_date and end_date:
            filename = f"reports_{start_date.replace('-', '')}_{end_date.replace('-', '')}.csv"
        else:
            filename = f"reports_{datetime.date.today().strftime('%Y%m%d')}.csv"

        # レスポンスを作成
        response = make_response(output_buffer.getvalue())
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"

        return response

    except Exception as e:
        return f"CSV出力エラー: {str(e)}", 500


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


# 写真削除管理画面
@app.route("/admin/photo-cleanup")
def photo_cleanup_admin():
    if "user_id" not in session:
        return redirect("/login")

    user = User.get_by_id(session["user_id"])
    if user.role != "admin":
        return "アクセス権限がありません", 403

    # 写真統計情報を取得
    from datetime import datetime, timedelta

    # 現在の写真数
    total_reports_with_photos = Report.select().where(Report.photo_upload_date.is_null(False)).count()

    # 60日以上前の写真数
    cutoff_date = datetime.now() - timedelta(days=PHOTO_CLEANUP_DAYS)
    cutoff_date_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")
    old_photos_count = (
        Report.select()
        .where((Report.photo_upload_date.is_null(False)) & (Report.photo_upload_date < cutoff_date_str))
        .count()
    )

    # 写真ディレクトリの総サイズを計算
    uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
    total_size = 0
    if os.path.exists(uploads_dir):
        for root, dirs, files in os.walk(uploads_dir):
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)

    # 削除対象の報告一覧
    old_reports = (
        Report.select()
        .where((Report.photo_upload_date.is_null(False)) & (Report.photo_upload_date < cutoff_date_str))
        .order_by(Report.photo_upload_date)
    )

    return render_template(
        "photo_cleanup_admin.html",
        user=user,
        total_reports_with_photos=total_reports_with_photos,
        old_photos_count=old_photos_count,
        total_size=total_size,
        cutoff_date=cutoff_date_str,
        old_reports=old_reports,
        cleanup_days=PHOTO_CLEANUP_DAYS,
        cleanup_enabled=PHOTO_CLEANUP_ENABLED,
    )


# 手動写真削除実行
@app.route("/admin/photo-cleanup/execute", methods=["POST"])
def execute_photo_cleanup():
    if "user_id" not in session:
        return redirect("/login")

    user = User.get_by_id(session["user_id"])
    if user.role != "admin":
        return "アクセス権限がありません", 403

    try:
        # 削除実行
        result = cleanup_old_photos(PHOTO_CLEANUP_DAYS)

        if result:
            return render_template("photo_cleanup_result.html", user=user, result=result, success=True)
        else:
            return render_template(
                "photo_cleanup_result.html",
                user=user,
                result=None,
                success=False,
                error_message="写真削除処理でエラーが発生しました",
            )
    except Exception as e:
        return render_template(
            "photo_cleanup_result.html",
            user=user,
            result=None,
            success=False,
            error_message=f"エラー: {str(e)}",
        )


if __name__ == "__main__":
    # エラーを防ぐため、より安全な設定で起動
    try:
        app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=True, threaded=True)
    except Exception as e:
        print(f"サーバー起動エラー: {e}")
        print("自動リロードを無効化して再起動します...")
        app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False, threaded=True)
