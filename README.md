# 平泉ハンターレポート

猟友会報告システム

## 環境設定

### 管理者権限認証パスワード

編集者・管理者権限を取得する際に必要なパスワードを設定できます。

環境変数で設定する場合：
```bash
export ADMIN_AUTH_PASSWORD=your_secure_password_here
```

または、app.py内の`ADMIN_AUTH_PASSWORD`変数を直接変更してください。

### メール設定（オプション）

.envファイルを作成して以下の設定を追加できます：

```
ADMIN_AUTH_PASSWORD=your_secure_password_here
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_DEFAULT_SENDER=your_email@gmail.com
YAKUBA_EMAIL=yakuba@example.com
```

## 使用方法

1. アプリケーションを起動
2. 新規登録画面でユーザーを作成
3. 編集者・管理者権限を取得する場合は、管理者権限認証パスワードが必要
