FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 8501
CMD ["python3", "-X", "faulthandler", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0"]