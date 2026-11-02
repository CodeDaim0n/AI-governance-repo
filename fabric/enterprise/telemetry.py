import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from prometheus_client import Counter,Gauge,generate_latest
DECISIONS=Counter('fabric_decisions','Governed business decisions',['outcome'])
DEPENDENCIES=Counter('fabric_dependency_failures','Runtime authoritative dependency failures')
OUTBOX=Gauge('fabric_outbox_pending','Undelivered transactional outbox records')
def setup():
 provider=TracerProvider(resource=Resource.create({'service.name':'fabric-gateway'}))
 provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=os.environ['OTEL_ENDPOINT'])))
 trace.set_tracer_provider(provider)
 return trace.get_tracer('fabric.enterprise')
