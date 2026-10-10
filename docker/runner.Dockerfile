FROM python:3.12-slim
RUN pip install --no-cache-dir pandas numpy scipy scikit-learn statsmodels matplotlib seaborn openpyxl python-docx pypdf reportlab pyarrow
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MPLCONFIGDIR=/tmp/matplotlib
WORKDIR /outputs
USER 65534:65534
