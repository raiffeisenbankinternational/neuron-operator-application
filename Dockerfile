FROM artifacts.rbi.tech/cortex-docker-host/raiffeisen/cortex-pipeline-application/python:2023.04.24

COPY requirements.txt /src/requirements.txt
RUN pip install -r /src/requirements.txt

COPY operator /operator

ENTRYPOINT ["kopf", "run", "/operator/operator.py"]
