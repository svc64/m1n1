from m1n1.trace.sep import SEPTracer
from m1n1.trace.dart import DARTTracer

dart_tracer = DARTTracer(hv, "/arm-io/dart-sep", verbose=1)
dart_tracer.start()
sep_tracer = SEPTracer(hv, "/arm-io/sep", verbose=1)
sep_tracer.start(dart=dart_tracer.dart)
