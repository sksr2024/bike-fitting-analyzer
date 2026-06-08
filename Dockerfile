FROM public.ecr.aws/lambda/python:3.12

# opencv-python-headless が必要とする共有ライブラリ
RUN dnf install -y libgl1 mesa-libGL 2>/dev/null || true

# Python 依存ライブラリをインストール
COPY lambda/inference/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# アプリケーションコードをコピー
COPY inference.py ${LAMBDA_TASK_ROOT}/
COPY lambda/inference/handler.py ${LAMBDA_TASK_ROOT}/

# models/movenet_lightning.onnx をビルド時に含める場合:
# COPY models/movenet_lightning.onnx ${LAMBDA_TASK_ROOT}/models/

CMD ["handler.lambda_handler"]
