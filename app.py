from flask import Flask, render_template, request, redirect, session, url_for
from peewee import Model, CharField, SqliteDatabase
from werkzeug.security import generate_password_hash, check_password_hash

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

# DB初期化
db.connect()
db.create_tables([User])

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
    return f"ようこそ、{user.name}さん（{user.role}）"

# ログアウト処理
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    app.run(debug=True)
