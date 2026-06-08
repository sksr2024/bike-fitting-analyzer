# Bike Fitting Analyzer

![Python](https://img.shields.io/badge/Python-3.12-blue)
![AWS Lambda](https://img.shields.io/badge/AWS-Lambda-orange)
![Terraform](https://img.shields.io/badge/IaC-Terraform-%235835CC)
![CI](https://github.com/sksr2024/bike-fitting-analyzer/actions/workflows/ci.yml/badge.svg)

自転車に乗っている画像をアップロードするだけで、AI が姿勢を解析し、膝・股関節・肘・肩の 8 関節角度を自動計測するサーバーレス Web アプリです。

## アーキテクチャ

```
ブラウザ
  ├── CloudFront → S3（静的フロントエンド）
  └── API Gateway  POST /analyze
        └── API Lambda（Python 3.12）
              ├── S3 に入力画像を保存
              └── 推論 Lambda（Docker / ONNX Runtime）を同期呼び出し
                    ├── MoveNet で 17 点のキーポイントを検出
                    ├── 8 関節の角度を算出
                    └── アノテーション済み画像を S3 に保存
```

## 技術スタック

| カテゴリ | 技術 |
|---|---|
| ML 推論 | MoveNet Lightning（ONNX Runtime） |
| 画像処理 | OpenCV |
| バックエンド | AWS Lambda（Python 3.12）、Amazon API Gateway HTTP API |
| ストレージ | Amazon S3（入力画像・出力画像） |
| CDN | Amazon CloudFront |
| コンテナ | Docker、Amazon ECR |
| IaC | Terraform（AWS Provider >= 5.0） |
| CI/CD | GitHub Actions |

## 検出できる関節角度

| キー | 関節 | 計測点 |
|---|---|---|
| L_knee | 左膝 | 腰→膝→足首 |
| R_knee | 右膝 | 腰→膝→足首 |
| L_hip | 左股関節 | 肩→腰→膝 |
| R_hip | 右股関節 | 肩→腰→膝 |
| L_elbow | 左肘 | 肩→肘→手首 |
| R_elbow | 右肘 | 肩→肘→手首 |
| L_shoulder | 左肩 | 肘→肩→腰 |
| R_shoulder | 右肩 | 肘→肩→腰 |

## セットアップ

### 前提条件

- Python 3.12
- Docker
- Terraform >= 1.0
- AWS CLI（認証済み）

### ローカル実行

```bash
python -m venv .venv && source .venv/bin/activate
pip install onnxruntime opencv-python numpy

# models/ に movenet_lightning.onnx を配置（.gitignore 対象のため別途取得）
python inference.py test_images/sample.jpg
# → test_images/result.png に骨格・角度を描画した画像が出力される
```

### テスト実行

```bash
pip install -r requirements-dev.txt
pytest -v
```

### AWS デプロイ

```bash
# 1. 推論 Lambda のコンテナイメージをビルド & ECR にプッシュ
docker build -t bike-fitting-inference .
aws ecr get-login-password --region ap-northeast-1 | \
  docker login --username AWS --password-stdin <ECR_URL>
docker tag bike-fitting-inference <ECR_URL>:latest
docker push <ECR_URL>:latest

# 2. Terraform でインフラを構築
cd terraform
terraform init
terraform apply -var="alert_email=your@example.com"
```

## コスト試算

月間コスト上限を **$5 USD** に設定しています（`terraform/budget.tf`）。  
80% と 100% 到達時にメール通知が届きます。

## API リファレンス

### POST /analyze

**リクエスト:**

```json
{
  "image": "<Base64 エンコードされた画像データ>"
}
```

Content-Type: `application/json`  
最大サイズ: 10 MB

**レスポンス (200):**

```json
{
  "result_url": "https://...(署名付き URL、有効期限 1 時間)",
  "result_key": "results/xxxxxxxx.jpg",
  "angles": {
    "L_knee": 145.2,
    "R_knee": 143.8,
    "L_hip": 72.5,
    "R_hip": 71.0,
    "L_elbow": 158.3,
    "R_elbow": 157.9,
    "L_shoulder": 89.1,
    "R_shoulder": 88.4
  }
}
```
