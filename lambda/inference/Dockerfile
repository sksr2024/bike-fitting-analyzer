FROM public.ecr.aws/lambda/python:3.12

# OpenCVの依存ライブラリ
RUN dnf install -y mesa-libGL && dnf clean all

# Pythonパッケージをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# モデルファイルをコピー
COPY movenet_lightning.onnx /opt/ml/model/movenet_lightning.onnx

# ハンドラーをコピー
COPY handler.py ${LAMBDA_TASK_ROOT}/

CMD ["handler.lambda_handler"]
