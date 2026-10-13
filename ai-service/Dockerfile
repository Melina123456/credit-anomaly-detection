FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
# recorded on every trained model; passed in because the image has no .git
ARG GIT_COMMIT=
ENV GIT_COMMIT=$GIT_COMMIT
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]