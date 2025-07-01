from flask import Flask, request, jsonify
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
import requests
import logging
import os

logging.basicConfig(filename='/app/app.log', level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

JAEGER_ENDPOINT = os.getenv('JAEGER_ENDPOINT', 'http://jaeger:4318/v1/traces')

try:
    resource = Resource(attributes={"service.name": "gateway"})
    trace.set_tracer_provider(TracerProvider(resource=resource))
    otlp_exporter = OTLPSpanExporter(endpoint=JAEGER_ENDPOINT)
    span_processor = BatchSpanProcessor(otlp_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)
    tracer = trace.get_tracer(__name__)
    FlaskInstrumentor().instrument_app(app)
    RequestsInstrumentor().instrument()
    logger.info("Gateway: Initialized OpenTelemetry with Jaeger at %s", JAEGER_ENDPOINT)
except Exception as e:
    logger.error("Gateway: Failed to initialize OpenTelemetry: %s", str(e))
    raise

@app.route('/api/login', methods=['POST'])
def login():
    with tracer.start_as_current_span("gateway-login") as span:
        try:
            data = request.get_json()
            username = data.get('username')
            span.set_attribute("user.username", username)
            response = requests.post('http://auth-service:5001/auth', json=data)
            return jsonify(response.json()), response.status_code
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error("Gateway: Error for %s: %s", username or "unknown", str(e))
            return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=8080)
    finally:
        trace.get_tracer_provider().force_flush()