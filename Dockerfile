FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
COPY samples ./samples
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -e . \
 && useradd -r -u 10001 appuser && mkdir -p /data && chown -R appuser /app /data
USER appuser
VOLUME /data
ENTRYPOINT ["python", "-m", "sales_etl"]
CMD ["samples/pos_daily.csv", "samples/shopify_orders.csv", "samples/yoco_payments.csv", "--db", "/data/reporting.db"]
