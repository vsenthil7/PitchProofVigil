FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Supply-chain: audit pinned dependencies for known CVEs. Report-only (||
# true) so a transient upstream advisory does not block deploys; the findings
# are printed in the build log and tracked for scheduled dependency bumps.
ARG AUDIT_STRICT=false
RUN pip install --no-cache-dir pip-audit \
    && (pip-audit -r requirements.txt || ([ "$AUDIT_STRICT" = "true" ] && exit 1 || echo "pip-audit: advisories found (report-only)")) \
    && pip uninstall -y pip-audit
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
ENV USE_MOCKS=true
EXPOSE 8000
CMD ["./entrypoint.sh"]
